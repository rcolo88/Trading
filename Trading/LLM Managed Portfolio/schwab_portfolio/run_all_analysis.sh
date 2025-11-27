#!/bin/bash
###############################################################################
# Run All Analysis Script
# Executes complete agent pipeline to generate trading recommendations
#
# Workflow:
# 1. Generate portfolio report (main.py --report-only)
# 2. Run news analysis (news_analysis_script.py)
# 3. Run quality analysis (quality_analysis_script.py)
# 4. Generate trading recommendations (recommendation_generator_script.py)
#
# Usage:
#   ./run_all_analysis.sh           # Full analysis (daily)
#   ./run_all_analysis.sh --weekly  # Include watchlist generation (weekly)
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Check for weekly flag
WEEKLY=false
if [[ "$1" == "--weekly" ]]; then
    WEEKLY=true
fi

echo ""
echo "================================================================"
echo "  LLM PORTFOLIO AGENT ANALYSIS PIPELINE"
echo "================================================================"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Mode: $(if $WEEKLY; then echo 'WEEKLY (includes watchlist generation)'; else echo 'DAILY (standard analysis)'; fi)"
echo "================================================================"
echo ""

###############################################################################
# Step 0: Environment Check
###############################################################################
echo -e "${BLUE}[0/5]${NC} Checking environment..."

# Check for FINNHUB_API_KEY
if [ -z "$FINNHUB_API_KEY" ]; then
    echo -e "${YELLOW}WARNING: FINNHUB_API_KEY not set${NC}"
    echo "News analysis will be skipped. Get a free key at: https://finnhub.io/"
    echo "Set it with: export FINNHUB_API_KEY='your_key_here'"
    SKIP_NEWS=true
else
    echo -e "${GREEN}✓${NC} FINNHUB_API_KEY is set"
    SKIP_NEWS=false
fi

# Check for Python
if ! command -v python &> /dev/null; then
    echo -e "${RED}ERROR: Python not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Environment check complete"
echo ""

###############################################################################
# Step 1: Generate Portfolio Report
###############################################################################
echo -e "${BLUE}[1/5]${NC} Generating portfolio report..."
echo "Command: python \"$PARENT_DIR/Portfolio Scripts Schwab/main.py\" --report-only"

if python "$SCRIPT_DIR/main.py" --report-only; then
    echo -e "${GREEN}✓${NC} Portfolio report generated successfully"
else
    echo -e "${YELLOW}WARNING: Portfolio report generation failed${NC}"
    echo "Continuing with analysis..."
fi
echo ""

###############################################################################
# Step 2: News Analysis
###############################################################################
if [ "$SKIP_NEWS" = false ]; then
    echo -e "${BLUE}[2/5]${NC} Running news sentiment analysis..."
    echo "Command: python \"$SCRIPT_DIR/news_analysis_script.py\""

    if python "$SCRIPT_DIR/news_analysis_script.py"; then
        echo -e "${GREEN}✓${NC} News analysis complete"
    else
        echo -e "${YELLOW}WARNING: News analysis failed${NC}"
        echo "Continuing with quality analysis..."
    fi
else
    echo -e "${YELLOW}[2/5] Skipping news analysis (no API key)${NC}"
fi
echo ""

###############################################################################
# Step 3: Quality Analysis
###############################################################################
echo -e "${BLUE}[3/5]${NC} Running quality metrics analysis..."
echo "Command: python \"$SCRIPT_DIR/quality_analysis_script.py\""

if python "$SCRIPT_DIR/quality_analysis_script.py"; then
    echo -e "${GREEN}✓${NC} Quality analysis complete"
else
    echo -e "${RED}ERROR: Quality analysis failed${NC}"
    echo "Cannot continue without quality analysis. Exiting."
    exit 1
fi
echo ""

###############################################################################
# Step 3.5: Weekly Watchlist Generation (optional)
###############################################################################
if [ "$WEEKLY" = true ]; then
    echo -e "${BLUE}[3.5/5]${NC} Running weekly watchlist generation..."
    echo "Command: python \"$SCRIPT_DIR/watchlist_generator_script.py\""
    echo "NOTE: This may take 10-15 minutes for full S&P 500 screening"

    if python "$SCRIPT_DIR/watchlist_generator_script.py"; then
        echo -e "${GREEN}✓${NC} Watchlist generation complete"
    else
        echo -e "${YELLOW}WARNING: Watchlist generation failed${NC}"
        echo "Continuing with recommendation generation..."
    fi
    echo ""
fi

###############################################################################
# Step 4: Generate Trading Recommendations
###############################################################################
echo -e "${BLUE}[4/5]${NC} Generating trading recommendations..."
echo "Command: python \"$SCRIPT_DIR/recommendation_generator_script.py\""

if python "$SCRIPT_DIR/recommendation_generator_script.py"; then
    echo -e "${GREEN}✓${NC} Trading recommendations generated"
else
    echo -e "${RED}ERROR: Recommendation generation failed${NC}"
    exit 1
fi
echo ""

###############################################################################
# Step 5: Summary
###############################################################################
echo ""
echo "================================================================"
echo "  ANALYSIS PIPELINE COMPLETE"
echo "================================================================"
echo "Finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
echo "Generated Files:"
echo "----------------------------------------------------------------"

# Find latest outputs
TIMESTAMP=$(date '+%Y%m%d')
NEWS_FILE="$SCRIPT_DIR/outputs/news_analysis_${TIMESTAMP}_summary.txt"
QUALITY_FILE="$SCRIPT_DIR/outputs/quality_analysis_${TIMESTAMP}_summary.txt"
WATCHLIST_FILE="$SCRIPT_DIR/outputs/quality_watchlist_${TIMESTAMP}_summary.txt"
RECOMMENDATIONS_FILE="$PARENT_DIR/trading_recommendations/trading_recommendations_${TIMESTAMP}.md"

if [ -f "$NEWS_FILE" ]; then
    echo -e "${GREEN}✓${NC} News Analysis:        $NEWS_FILE"
else
    echo -e "${YELLOW}○${NC} News Analysis:        (skipped)"
fi

if [ -f "$QUALITY_FILE" ]; then
    echo -e "${GREEN}✓${NC} Quality Analysis:     $QUALITY_FILE"
else
    echo -e "${RED}✗${NC} Quality Analysis:     NOT FOUND"
fi

if [ "$WEEKLY" = true ] && [ -f "$WATCHLIST_FILE" ]; then
    echo -e "${GREEN}✓${NC} Watchlist (Weekly):   $WATCHLIST_FILE"
fi

if [ -f "$RECOMMENDATIONS_FILE" ]; then
    echo -e "${GREEN}✓${NC} Trading Recommendations: $RECOMMENDATIONS_FILE"
    echo ""
    echo "================================================================"
    echo "  NEXT STEPS"
    echo "================================================================"
    echo "1. Review trading recommendations:"
    echo "   cat \"$RECOMMENDATIONS_FILE\""
    echo ""
    echo "2. If approved, edit manual_trades_override.json:"
    echo "   - Copy approved trades from recommendations"
    echo "   - Set \"enabled\": true"
    echo ""
    echo "3. Execute trades (requires market hours):"
    echo "   python \"$PARENT_DIR/Portfolio Scripts Schwab/main.py\""
    echo ""
else
    echo -e "${RED}✗${NC} Trading Recommendations: NOT FOUND"
fi

echo "================================================================"
echo ""

# Exit with success
exit 0
