# Enhanced Base Agent - Technical Documentation

## Overview

The enhanced `base_agent.py` provides a robust foundation for HuggingFace Inference API interactions with production-grade features including intelligent retry logic, in-memory caching, and comprehensive error handling.

## Key Features

### 1. Smart Retry Logic

The agent implements sophisticated retry logic tailored to HuggingFace API behavior:

#### HTTP 503 - Model Loading
```python
# Special handling for model loading (cold start)
wait_time = random.uniform(20, 30)  # Random 20-30 second wait
```
- **Scenario**: First API call after model inactivity
- **Behavior**: Wait 20-30 seconds (models need time to load into memory)
- **Retries**: Up to 3 attempts
- **Logging**: Warning level with attempt counter

#### HTTP 429 - Rate Limiting
```python
# Respect Retry-After header
retry_after = response.headers.get('Retry-After')
wait_time = int(retry_after) if retry_after else 60
```
- **Scenario**: Free tier rate limit exceeded
- **Behavior**: Respects `Retry-After` header, defaults to 60s
- **Retries**: Up to 3 attempts
- **Logging**: Warning level with wait time

#### Network Errors
```python
# Exponential backoff for connection/timeout errors
delay = base_delay * (exponential_base ** attempt)
```
- **Scenarios**: Timeout, ConnectionError, RequestException
- **Behavior**: Exponential backoff (1s, 2s, 4s)
- **Retries**: Up to 3 attempts
- **Logging**: Error level with retry information

#### Never Crashes
```python
def _make_api_call(self, payload: dict, bypass_cache: bool = False) -> Optional[Dict[str, Any]]:
    # Returns None on all errors - NEVER raises exceptions
```
All errors are caught and logged, returning `None` instead of raising exceptions.

### 2. In-Memory Caching System

#### SimpleCache Class
```python
class SimpleCache:
    def __init__(self, ttl_seconds: int = 300):  # 5-minute TTL
        self._cache: OrderedDict[str, Tuple[Any, datetime]] = OrderedDict()
        self.ttl_seconds = ttl_seconds
        self.max_size = 100  # LRU eviction
```

**Features**:
- **TTL-based expiration**: 5-minute default (configurable)
- **LRU eviction**: Removes oldest entries when full (max 100 entries)
- **Automatic cleanup**: Expired entries removed on access
- **Shared across agents**: Single cache instance for all agents

#### Cache Key Generation
```python
def _generate_cache_key(self, text: str) -> str:
    content = f"{self.model_config.model_id}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()
```
- Hash of model ID + input text
- Same text analyzed by different models = different cache keys
- SHA-256 ensures consistent key generation

#### Cache Operations
```python
# Get from cache (returns None if not found/expired)
cached = self._cache.get(cache_key)

# Set in cache
self._cache.set(cache_key, result)

# Clear all cache entries
BaseAgent.clear_cache()

# Get cache statistics
stats = BaseAgent.get_cache_stats()
```

### 3. Classification Response Parsing

#### Robust Parser
```python
def _parse_classification_response(self, response: Any) -> Optional[Dict[str, Any]]:
    # Handles: [{"label": "positive", "score": 0.95}]
    # Or:      [[{"label": "positive", "score": 0.95}]]
    # Returns: {"label": "positive", "score": 0.95} or None
```

**Handles**:
- Single-level lists: `[{"label": "...", "score": 0.95}]`
- Nested lists: `[[{"label": "...", "score": 0.95}]]`
- Invalid formats: Returns `None` instead of crashing
- Type validation: Checks for dict with required keys

### 4. Comprehensive Logging

#### Log Levels
```python
# DEBUG: Cache hits, API attempts, response parsing
self.logger.debug(f"Cache hit for key: {key[:20]}...")

# INFO: Successful operations
self.logger.info(f"API call successful for {self.model_config.name}")

# WARNING: Retryable errors
self.logger.warning(f"Model loading (503), waiting {wait_time:.1f}s")

# ERROR: Failures that return neutral results
self.logger.error(f"API call failed after {max_retries} attempts")
```

#### What Gets Logged
1. **Cache operations**: Hits, misses, sets, evictions
2. **API attempts**: Each retry attempt with reason
3. **Retry logic**: Wait times and retry counts
4. **Errors**: All exceptions with context
5. **Response parsing**: Success and failures
6. **Performance**: Cache statistics

### 5. Error Handling Flow

```
User calls analyze()
        ↓
_make_api_call() → Returns None on error
        ↓
Check if response is None → Return neutral AgentResult
        ↓
_parse_classification_response() → Returns None on parse error
        ↓
Check if parsed is None → Return neutral AgentResult
        ↓
_interpret_results() → Create AgentResult
        ↓
Return result to user
```

**Key principle**: Never crash, always return a neutral result with error information.

## Usage Examples

### Basic Usage
```python
from agents import NewsAgent

agent = NewsAgent()
result = agent.analyze("Apple reports strong earnings")

print(f"Sentiment: {result.sentiment}")
print(f"Confidence: {result.confidence:.2%}")
```

### With Caching
```python
# First call - hits API
result1 = agent.analyze(text)  # Takes ~2-5 seconds

# Second call - uses cache
result2 = agent.analyze(text)  # Instant (<0.01 seconds)
```

### Cache Management
```python
# Check cache stats
stats = BaseAgent.get_cache_stats()
print(f"Cache size: {stats['cache_size']}/{stats['max_size']}")
print(f"TTL: {stats['ttl_seconds']} seconds")

# Clear cache if needed
BaseAgent.clear_cache()
```

### Bypass Cache
```python
# Force fresh API call
response = agent._make_api_call(payload, bypass_cache=True)
```

### Error Handling
```python
result = agent.analyze(text)

# Check for errors
if result.confidence == 0.0 and result.label in ["ERROR", "PARSE_ERROR"]:
    print(f"Analysis failed: {result.reasoning}")
else:
    print(f"Valid result: {result.sentiment} ({result.confidence:.2%})")
```

## Configuration

### Retry Settings (hf_config.py)
```python
RETRY = RetryConfig(
    max_retries=3,           # Maximum retry attempts
    base_delay=1.0,          # Initial delay for exponential backoff
    max_delay=60.0,          # Maximum delay between retries
    exponential_base=2.0     # Exponential growth factor
)
```

### Cache Settings (base_agent.py)
```python
_cache = SimpleCache(
    ttl_seconds=300,  # 5 minutes
    max_size=100      # Maximum entries
)
```

## Performance Characteristics

### Without Cache
- **First call**: 2-5 seconds (API latency)
- **503 errors**: Additional 20-30 seconds per retry
- **429 errors**: Additional 60+ seconds per retry

### With Cache
- **Cache hit**: <0.01 seconds (instant)
- **Cache miss**: Same as without cache
- **Memory usage**: ~1-2KB per cached entry
- **Max memory**: ~100-200KB for full cache

## Testing

Run the test suite:
```bash
cd "Portfolio Scripts Schwab"
python test_enhanced_agents.py
```

Tests cover:
1. Basic sentiment analysis
2. Cache performance (speedup measurement)
3. Cache expiry behavior
4. Shared cache across agents
5. Error handling and recovery

## Migration from Original

### Changes to Child Agents

**Old pattern (raises exceptions)**:
```python
try:
    response = self._make_api_call(payload)
    result = self._interpret_results(response, text, context)
    return result
except Exception as e:
    return error_result
```

**New pattern (never raises)**:
```python
response = self._make_api_call(payload)
if response is None:
    return error_result

parsed = self._parse_classification_response(response)
if parsed is None:
    return error_result

result = self._interpret_results(parsed, text, context)
return result
```

### Breaking Changes
- `_make_api_call()` returns `Optional[Dict]` (can be None)
- `_interpret_results()` receives parsed dict, not raw response
- No exceptions are raised from API calls

## Best Practices

1. **Always check for None**: After `_make_api_call()` and `_parse_classification_response()`
2. **Use cache wisely**: Don't bypass cache unless you need fresh data
3. **Monitor cache stats**: Use `get_cache_stats()` to tune cache size
4. **Handle low confidence**: Check `confidence` and `label` for errors
5. **Log appropriately**: Use DEBUG for verbose, INFO for important events

## Production Considerations

### Free Tier Limits
- ~30 requests/hour per model without token
- Higher limits with HuggingFace token
- Caching reduces API calls significantly

### Scaling
- Cache is in-memory (lost on restart)
- Consider Redis for distributed caching
- Monitor cache hit rate for optimization

### Monitoring
```python
# Log cache efficiency
stats = BaseAgent.get_cache_stats()
logger.info(f"Cache utilization: {stats['cache_size']}/{stats['max_size']}")
```

## Summary

The enhanced base agent provides:

✅ **503 errors**: Smart 20-30s wait for model loading
✅ **429 errors**: Respects Retry-After header
✅ **Network errors**: Exponential backoff
✅ **In-memory cache**: 5-minute TTL with LRU eviction
✅ **Never crashes**: Returns None on all errors
✅ **Comprehensive logging**: DEBUG, INFO, WARNING, ERROR levels
✅ **Type-safe**: Full type hints throughout
✅ **Production-ready**: Tested and documented

This implementation provides a robust foundation for production financial sentiment analysis with HuggingFace models.
