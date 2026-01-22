"""
Progress Tracker for Multi-Day Processing Sessions

Provides SQLite-based persistence for tracking progress across multi-day
stock analysis sessions. Enables resume capability and session management.

Key Features:
- Per-stock progress tracking with timestamps
- Session-level API call tracking
- Quarterly data freshness monitoring
- Resume capability from interruption points
- Progress analytics and ETA calculations

Author: Progress Tracking System
Date: January 2026
"""

import sqlite3
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StockProgress:
    """Progress tracking for individual stock"""
    ticker: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    last_updated: datetime
    quarter: int  # Quarter number when last updated
    api_calls_used: int
    error_message: Optional[str] = None
    quality_score: Optional[float] = None
    processing_time_seconds: Optional[float] = None


@dataclass
class SessionProgress:
    """Progress tracking for processing session"""
    session_id: str
    session_date: datetime
    stocks_processed: int
    stocks_failed: int
    api_calls_used: int
    session_duration_seconds: Optional[float] = None
    status: str = 'active'  # 'active', 'completed', 'failed'


@dataclass
class ProgressState:
    """Overall progress state"""
    total_stocks: int
    completed_stocks: int
    failed_stocks: int
    pending_stocks: int
    last_session: Optional[SessionProgress] = None
    api_calls_today: int = 0
    api_calls_remaining: int = 250


class ProgressTracker:
    """
    SQLite-based progress tracking for multi-day processing sessions.
    
    Manages persistence of stock-level and session-level progress,
    enabling resume capability and detailed analytics.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize progress tracker with SQLite database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database schema
        self._init_database()
        
        logger.info(f"ProgressTracker initialized with database: {self.db_path}")
    
    def _init_database(self) -> None:
        """Initialize SQLite database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Stock progress table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_progress (
                    ticker TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    quarter INTEGER NOT NULL,
                    api_calls_used INTEGER DEFAULT 0,
                    error_message TEXT,
                    quality_score REAL,
                    processing_time_seconds REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Session progress table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_progress (
                    session_id TEXT PRIMARY KEY,
                    session_date TEXT NOT NULL,
                    stocks_processed INTEGER DEFAULT 0,
                    stocks_failed INTEGER DEFAULT 0,
                    api_calls_used INTEGER DEFAULT 0,
                    session_duration_seconds REAL,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    completed_at TEXT
                )
            ''')
            
            # Daily API usage table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_usage (
                    date TEXT PRIMARY KEY,
                    api_calls_used INTEGER DEFAULT 0,
                    stocks_processed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_status ON stock_progress(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_updated ON stock_progress(last_updated)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_date ON session_progress(session_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_usage_date ON daily_usage(date)')
            
            conn.commit()
    
    def save_stock_progress(self, progress: StockProgress) -> None:
        """
        Save progress for a single stock.
        
        Args:
            progress: StockProgress object to save
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO stock_progress 
                (ticker, status, last_updated, quarter, api_calls_used, 
                 error_message, quality_score, processing_time_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                progress.ticker,
                progress.status,
                progress.last_updated.isoformat(),
                progress.quarter,
                progress.api_calls_used,
                progress.error_message,
                progress.quality_score,
                progress.processing_time_seconds
            ))
            
            conn.commit()
        
        logger.debug(f"Saved progress for {progress.ticker}: {progress.status}")
    
    def get_stock_progress(self, ticker: str) -> Optional[StockProgress]:
        """
        Get progress for a single stock.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            StockProgress object or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ticker, status, last_updated, quarter, api_calls_used,
                       error_message, quality_score, processing_time_seconds
                FROM stock_progress WHERE ticker = ?
            ''', (ticker,))
            
            row = cursor.fetchone()
            if row:
                return StockProgress(
                    ticker=row[0],
                    status=row[1],
                    last_updated=datetime.fromisoformat(row[2]),
                    quarter=row[3],
                    api_calls_used=row[4],
                    error_message=row[5],
                    quality_score=row[6],
                    processing_time_seconds=row[7]
                )
        
        return None
    
    def get_stocks_by_status(self, status: str) -> List[str]:
        """
        Get list of tickers with specific status.
        
        Args:
            status: Status to filter by ('pending', 'completed', 'failed', 'processing')
            
        Returns:
            List of ticker symbols
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT ticker FROM stock_progress WHERE status = ?', (status,))
            return [row[0] for row in cursor.fetchall()]
    
    def get_completed_tickers(self) -> List[str]:
        """Get list of successfully completed tickers"""
        return self.get_stocks_by_status('completed')
    
    def get_failed_tickers(self) -> List[str]:
        """Get list of failed tickers"""
        return self.get_stocks_by_status('failed')
    
    def get_pending_tickers(self) -> List[str]:
        """Get list of pending tickers"""
        return self.get_stocks_by_status('pending')
    
    def is_completed(self, ticker: str) -> bool:
        """Check if a ticker has been successfully completed"""
        progress = self.get_stock_progress(ticker)
        return progress is not None and progress.status == 'completed'
    
    def is_failed(self, ticker: str) -> bool:
        """Check if a ticker has failed"""
        progress = self.get_stock_progress(ticker)
        return progress is not None and progress.status == 'failed'
    
    def get_last_updated(self, ticker: str) -> Optional[datetime]:
        """Get the last update time for a ticker"""
        progress = self.get_stock_progress(ticker)
        return progress.last_updated if progress else None
    
    def save_session_start(self, session_queue) -> None:
        """
        Save the start of a new processing session.
        
        Args:
            session_queue: DailyQueue object with session information
        """
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = SessionProgress(
            session_id=session_id,
            session_date=session_queue.session_date,
            stocks_processed=0,
            stocks_failed=0,
            api_calls_used=session_queue.total_api_calls,
            status='active'
        )
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO session_progress 
                (session_id, session_date, stocks_processed, stocks_failed, 
                 api_calls_used, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session.session_id,
                session.session_date.isoformat(),
                session.stocks_processed,
                session.stocks_failed,
                session.api_calls_used,
                session.status
            ))
            
            conn.commit()
        
        logger.info(f"Started new session: {session_id}")
    
    def update_session_progress(self, session_id: str, ticker: str, 
                               success: bool, api_calls: int) -> None:
        """
        Update session progress after processing a stock.
        
        Args:
            session_id: Session identifier
            ticker: Stock ticker processed
            success: Whether processing was successful
            api_calls: API calls used for this stock
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if success:
                cursor.execute('''
                    UPDATE session_progress 
                    SET stocks_processed = stocks_processed + 1
                    WHERE session_id = ?
                ''', (session_id,))
            else:
                cursor.execute('''
                    UPDATE session_progress 
                    SET stocks_failed = stocks_failed + 1
                    WHERE session_id = ?
                ''', (session_id,))
            
            conn.commit()
    
    def get_session_progress(self, session_id: str) -> Optional[SessionProgress]:
        """Get progress for a specific session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT session_id, session_date, stocks_processed, stocks_failed,
                       api_calls_used, session_duration_seconds, status
                FROM session_progress WHERE session_id = ?
            ''', (session_id,))
            
            row = cursor.fetchone()
            if row:
                return SessionProgress(
                    session_id=row[0],
                    session_date=datetime.fromisoformat(row[1]),
                    stocks_processed=row[2],
                    stocks_failed=row[3],
                    api_calls_used=row[4],
                    session_duration_seconds=row[5],
                    status=row[6]
                )
        
        return None
    
    def get_latest_session(self) -> Optional[SessionProgress]:
        """Get the most recent session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT session_id, session_date, stocks_processed, stocks_failed,
                       api_calls_used, session_duration_seconds, status
                FROM session_progress 
                ORDER BY session_date DESC 
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            if row:
                return SessionProgress(
                    session_id=row[0],
                    session_date=datetime.fromisoformat(row[1]),
                    stocks_processed=row[2],
                    stocks_failed=row[3],
                    api_calls_used=row[4],
                    session_duration_seconds=row[5],
                    status=row[6]
                )
        
        return None
    
    def save_daily_usage(self, date: datetime, api_calls: int, stocks_processed: int) -> None:
        """
        Save daily API usage statistics.
        
        Args:
            date: Date for the usage record
            api_calls: Number of API calls used
            stocks_processed: Number of stocks processed
        """
        date_str = date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO daily_usage (date, api_calls_used, stocks_processed)
                VALUES (?, ?, COALESCE((SELECT stocks_processed FROM daily_usage WHERE date = ?), 0) + ?)
            ''', (date_str, api_calls, date_str, stocks_processed))
            
            conn.commit()
    
    def get_daily_usage(self, date: datetime) -> Tuple[int, int]:
        """
        Get daily API usage for a specific date.
        
        Args:
            date: Date to get usage for
            
        Returns:
            Tuple of (api_calls_used, stocks_processed)
        """
        date_str = date.strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT api_calls_used, stocks_processed 
                FROM daily_usage WHERE date = ?
            ''', (date_str,))
            
            row = cursor.fetchone()
            if row:
                return row[0], row[1]
        
        return 0, 0
    
    def get_session_calls_used(self) -> int:
        """Get API calls used in current session"""
        session = self.get_latest_session()
        return session.api_calls_used if session else 0
    
    def get_remaining_tickers(self, all_tickers: List[str]) -> List[str]:
        """
        Get list of tickers that still need to be processed.
        
        Args:
            all_tickers: Complete list of tickers for the index
            
        Returns:
            List of tickers that are not completed
        """
        completed = self.get_completed_tickers()
        return [ticker for ticker in all_tickers if ticker not in completed]
    
    def load_progress(self) -> ProgressState:
        """
        Load overall progress state.
        
        Returns:
            ProgressState object with current status
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get stock counts by status
            cursor.execute('SELECT status, COUNT(*) FROM stock_progress GROUP BY status')
            status_counts = dict(cursor.fetchall())
            
            # Get current session
            cursor.execute('''
                SELECT session_id, session_date, stocks_processed, stocks_failed,
                       api_calls_used, session_duration_seconds, status
                FROM session_progress 
                WHERE status = 'active'
                ORDER BY session_date DESC 
                LIMIT 1
            ''')
            
            session_row = cursor.fetchone()
            last_session = None
            if session_row:
                last_session = SessionProgress(
                    session_id=session_row[0],
                    session_date=datetime.fromisoformat(session_row[1]),
                    stocks_processed=session_row[2],
                    stocks_failed=session_row[3],
                    api_calls_used=session_row[4],
                    session_duration_seconds=session_row[5],
                    status=session_row[6]
                )
            
            # Get today's API usage
            today = datetime.now()
            api_calls_today, _ = self.get_daily_usage(today)
            
            total_stocks = sum(status_counts.values())
            
            return ProgressState(
                total_stocks=total_stocks,
                completed_stocks=status_counts.get('completed', 0),
                failed_stocks=status_counts.get('failed', 0),
                pending_stocks=status_counts.get('pending', 0),
                last_session=last_session,
                api_calls_today=api_calls_today,
                api_calls_remaining=max(0, 250 - api_calls_today)
            )
    
    def get_progress_summary(self) -> Dict:
        """Get detailed progress summary for reporting"""
        state = self.load_progress()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get recent sessions (last 7 days)
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute('''
                SELECT session_date, stocks_processed, stocks_failed, api_calls_used
                FROM session_progress 
                WHERE session_date >= ?
                ORDER BY session_date DESC
            ''', (seven_days_ago,))
            
            recent_sessions = [
                {
                    'date': row[0].split('T')[0],  # Extract date part
                    'processed': row[1],
                    'failed': row[2],
                    'api_calls': row[3]
                }
                for row in cursor.fetchall()
            ]
            
            # Get quality score statistics
            cursor.execute('''
                SELECT AVG(quality_score), MIN(quality_score), MAX(quality_score), 
                       COUNT(quality_score)
                FROM stock_progress 
                WHERE quality_score IS NOT NULL AND status = 'completed'
            ''')
            
            score_stats = cursor.fetchone()
            quality_stats = {}
            if score_stats and score_stats[3] > 0:
                quality_stats = {
                    'average_score': round(score_stats[0], 2),
                    'min_score': round(score_stats[1], 2),
                    'max_score': round(score_stats[2], 2),
                    'total_scored': score_stats[3]
                }
        
        return {
            'progress_state': asdict(state),
            'recent_sessions': recent_sessions,
            'quality_statistics': quality_stats,
            'completion_rate': round(state.completed_stocks / max(state.total_stocks, 1) * 100, 2)
        }