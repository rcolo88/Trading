"""
Quarterly Data Manager for Archive Rotation and Freshness

Manages quarterly data lifecycle including freshness detection, archive rotation,
and incremental summary updates. Ensures data quality while maintaining storage efficiency.

Key Features:
- 20-quarter (5-year) archive rotation
- Quarterly data freshness detection
- Incremental summary file updates (append-only)
- Automatic archive cleanup
- Historical data preservation

Author: Quarterly Data Management System
Date: January 2026
"""

import json
import logging
import shutil
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import re

logger = logging.getLogger(__name__)


class QuarterlyManager:
    """
    Manages quarterly data lifecycle for quality analysis system.
    
    Handles:
    - Detection of stale quarterly data
    - Rotation of summary archives
    - Incremental updates to analysis summaries
    - Archive maintenance (20-quarter retention)
    """
    
    MAX_QUARTERS_ARCHIVE = 20  # 5 years × 4 quarters = 20 quarters
    
    # Quarter boundaries (approximately)
    QUARTER_END_MONTHS = [3, 6, 9, 12]  # Mar, Jun, Sep, Dec
    QUARTER_END_DAYS = [31, 30, 30, 31]  # Days in each quarter-end month
    
    def __init__(self, outputs_dir: Path):
        """
        Initialize quarterly manager.
        
        Args:
            outputs_dir: Directory containing output files
        """
        self.outputs_dir = Path(outputs_dir)
        self.archive_dir = self.outputs_dir / "archive"
        
        # Ensure directories exist
        self.outputs_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
        
        # Main summary file path
        self.summary_file = self.outputs_dir / "quality_analysis_summary.txt"
        
        logger.info(f"QuarterlyManager initialized with outputs_dir: {self.outputs_dir}")
        logger.info(f"Archive directory: {self.archive_dir}")
    
    def get_current_quarter(self) -> int:
        """
        Get current quarter number (YYYYQ format, e.g., 20261 for 2026 Q1).
        
        Returns:
            Current quarter number
        """
        now = datetime.now()
        year = now.year
        
        # Determine quarter (1-4)
        if now.month <= 3:
            quarter = 1
        elif now.month <= 6:
            quarter = 2
        elif now.month <= 9:
            quarter = 3
        else:
            quarter = 4
        
        return year * 10 + quarter
    
    def quarter_to_date_range(self, quarter: int) -> Tuple[datetime, datetime]:
        """
        Convert quarter number to start and end dates.
        
        Args:
            quarter: Quarter number in YYYYQ format
            
        Returns:
            Tuple of (start_date, end_date)
        """
        year = quarter // 10
        q_num = quarter % 10
        
        if q_num == 1:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 3, 31, 23, 59, 59)
        elif q_num == 2:
            start_date = datetime(year, 4, 1)
            end_date = datetime(year, 6, 30, 23, 59, 59)
        elif q_num == 3:
            start_date = datetime(year, 7, 1)
            end_date = datetime(year, 9, 30, 23, 59, 59)
        else:  # q_num == 4
            start_date = datetime(year, 10, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
        
        return start_date, end_date
    
    def parse_quarter_from_summary(self, summary_content: str) -> Optional[int]:
        """
        Extract quarter number from summary file content.
        
        Args:
            summary_content: Content of summary file
            
        Returns:
            Quarter number or None if not found
        """
        # Look for quarter in generation date
        # Pattern: "Generated: 2026-01-20 12:47:02" -> extract quarter from date
        date_match = re.search(r'Generated: (\d{4})-(\d{2})-\d{2}', summary_content)
        if date_match:
            year = int(date_match.group(1))
            month = int(date_match.group(2))
            
            if month <= 3:
                quarter = 1
            elif month <= 6:
                quarter = 2
            elif month <= 9:
                quarter = 3
            else:
                quarter = 4
            
            return year * 10 + quarter
        
        return None
    
    def is_data_stale(self, last_updated: Optional[datetime], current_quarter: int) -> bool:
        """
        Check if data is from previous quarter (needs refresh).
        
        Args:
            last_updated: Last update timestamp
            current_quarter: Current quarter number
            
        Returns:
            True if data is stale, False if fresh
        """
        if last_updated is None:
            return True  # No data is considered stale
        
        # Extract quarter from last_updated
        year = last_updated.year
        month = last_updated.month
        
        if month <= 3:
            data_quarter = year * 10 + 1
        elif month <= 6:
            data_quarter = year * 10 + 2
        elif month <= 9:
            data_quarter = year * 10 + 3
        else:
            data_quarter = year * 10 + 4
        
        return data_quarter < current_quarter
    
    def archive_current_summary(self, current_quarter: Optional[int] = None) -> Optional[str]:
        """
        Archive current summary file if it's from a previous quarter.
        
        Args:
            current_quarter: Current quarter number (auto-detected if None)
            
        Returns:
            Path to archived file or None if no archive needed
        """
        if not self.summary_file.exists():
            return None
        
        if current_quarter is None:
            current_quarter = self.get_current_quarter()
        
        # Read current summary to check its quarter
        with open(self.summary_file, 'r') as f:
            content = f.read()
        
        summary_quarter = self.parse_quarter_from_summary(content)
        
        if summary_quarter is None or summary_quarter >= current_quarter:
            return None  # No archive needed
        
        # Archive the file
        archive_filename = f"quality_analysis_summary_Q{summary_quarter}.txt"
        archive_path = self.archive_dir / archive_filename
        
        try:
            shutil.copy2(self.summary_file, archive_path)
            logger.info(f"Archived summary to {archive_path}")
            return str(archive_path)
        except Exception as e:
            logger.error(f"Failed to archive summary: {e}")
            return None
    
    def rotate_old_archives(self) -> int:
        """
        Remove archives older than MAX_QUARTERS_ARCHIVE.
        
        Returns:
            Number of archives removed
        """
        current_quarter = self.get_current_quarter()
        cutoff_quarter = current_quarter - self.MAX_QUARTERS_ARCHIVE
        
        removed_count = 0
        
        try:
            for archive_file in self.archive_dir.glob("quality_analysis_summary_Q*.txt"):
                # Extract quarter from filename
                match = re.search(r'Q(\d{5})', archive_file.name)
                if match:
                    archive_quarter = int(match.group(1))
                    
                    if archive_quarter < cutoff_quarter:
                        archive_file.unlink()
                        removed_count += 1
                        logger.info(f"Removed old archive: {archive_file}")
        
        except Exception as e:
            logger.error(f"Error during archive rotation: {e}")
        
        return removed_count
    
    def create_new_summary_header(self, index_name: str, stocks_count: int) -> str:
        """
        Create header content for new summary file.
        
        Args:
            index_name: Name of the index being analyzed
            stocks_count: Number of stocks analyzed
            
        Returns:
            Header content string
        """
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_quarter = self.get_current_quarter()
        year = current_quarter // 10
        quarter = current_quarter % 10
        
        header = f"""============================================================
QUALITY ANALYSIS SUMMARY
============================================================
Generated: {current_time}
Index: {index_name}
Stocks Analyzed: {stocks_count}
Current Quarter: {year} Q{quarter}
============================================================

"""
        
        return header
    
    def parse_existing_summary_structure(self, content: str) -> Dict:
        """
        Parse existing summary file to extract structure and data.
        
        Args:
            content: Content of summary file
            
        Returns:
            Dictionary with parsed structure
        """
        lines = content.split('\n')
        
        structure = {
            'header_lines': [],
            'top_stocks_section': [],
            'distribution_sections': [],
            'other_lines': []
        }
        
        current_section = 'header'
        
        for line in lines:
            if 'TOP 20 STOCKS BY QUALITY SCORE:' in line:
                current_section = 'top_stocks'
            elif any(x in line for x in ['MARKET CAP DISTRIBUTION:', 'ROE PERSISTENCE SUMMARY:']):
                current_section = 'distribution'
            
            if current_section == 'header':
                structure['header_lines'].append(line)
            elif current_section == 'top_stocks':
                structure['top_stocks_section'].append(line)
            else:
                structure['distribution_sections'].append(line)
        
        return structure
    
    def extract_existing_tickers(self, content: str) -> set:
        """
        Extract set of tickers already in summary.
        
        Args:
            content: Content of summary file
            
        Returns:
            Set of ticker symbols
        """
        tickers = set()
        lines = content.split('\n')
        
        # Look for ticker lines in the TOP 20 section
        in_top_stocks = False
        for line in lines:
            if 'TOP 20 STOCKS BY QUALITY SCORE:' in line:
                in_top_stocks = True
                continue
            elif 'MARKET CAP DISTRIBUTION:' in line:
                in_top_stocks = False
                continue
            
            if in_top_stocks and line.strip():
                # Extract ticker (usually after rank number)
                parts = line.split()
                if len(parts) >= 2 and parts[1].isalpha() and len(parts[1]) <= 5:
                    tickers.add(parts[1])
        
        return tickers
    
    def merge_new_analysis(self, existing_content: str, new_analysis_data: List[Dict], 
                          index_name: str, total_stocks: int) -> str:
        """
        Merge new analysis data into existing summary content.
        
        Args:
            existing_content: Content of existing summary file
            new_analysis_data: New analysis results to merge
            index_name: Name of the index
            total_stocks: Total number of stocks analyzed
            
        Returns:
            Merged content string
        """
        # Parse existing structure
        structure = self.parse_existing_summary_structure(existing_content)
        existing_tickers = self.extract_existing_tickers(existing_content)
        
        # Filter out already analyzed tickers
        new_tickers = [item for item in new_analysis_data 
                      if item.get('ticker', '') not in existing_tickers]
        
        if not new_tickers:
            logger.info("No new tickers to merge")
            return existing_content
        
        # Create new header
        new_header = self.create_new_summary_header(index_name, total_stocks)
        
        # Merge top stocks section
        existing_top_stocks = structure['top_stocks_section']
        
        # Add new tickers to the list (sort by score)
        new_tickers.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        new_top_lines = []
        for i, item in enumerate(new_tickers[:20], 1):  # Top 20
            ticker = item.get('ticker', 'N/A')
            score = item.get('quality_score', 0)
            market_cap = item.get('market_cap', 'N/A')
            tier = item.get('tier', 'Unknown')
            red_flags = item.get('red_flags', 0)
            
            line = f"{i:<4} {ticker:<8} ${market_cap:<12} {score:<8.1f}    {tier:<12} {red_flags:<10}"
            new_top_lines.append(line)
        
        # Combine sections
        merged_content = new_header
        
        # Add existing top stocks (with separator)
        if existing_top_stocks:
            merged_content += '\n'.join(existing_top_stocks) + '\n'
            merged_content += '\n--- NEW ANALYSIS ---\n'
        
        # Add new top stocks
        if new_top_lines:
            merged_content += "Rank Ticker   Market Cap   Score    Tier         Red Flags \n"
            merged_content += "--------------------------------------------------------------------------------\n"
            merged_content += '\n'.join(new_top_lines) + '\n'
        
        # Add existing distribution sections
        merged_content += '\n'.join(structure['distribution_sections'])
        
        return merged_content
    
    def update_summary_incremental(self, new_analysis_data: List[Dict], 
                                  index_name: str, total_stocks: int) -> None:
        """
        Update summary file incrementally with new analysis data.
        
        Args:
            new_analysis_data: New analysis results
            index_name: Name of the index
            total_stocks: Total number of stocks analyzed
        """
        try:
            # Archive current summary if it's from previous quarter
            archived_path = self.archive_current_summary()
            
            # Rotate old archives
            removed_count = self.rotate_old_archives()
            if removed_count > 0:
                logger.info(f"Removed {removed_count} old archives")
            
            # Read existing content or create new
            if self.summary_file.exists():
                with open(self.summary_file, 'r') as f:
                    existing_content = f.read()
                
                # Merge new data
                merged_content = self.merge_new_analysis(
                    existing_content, new_analysis_data, index_name, total_stocks
                )
            else:
                # Create new summary
                merged_content = self.create_new_summary_header(index_name, total_stocks)
                
                # Add new data
                if new_analysis_data:
                    new_analysis_data.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
                    merged_content += "Rank Ticker   Market Cap   Score    Tier         Red Flags \n"
                    merged_content += "--------------------------------------------------------------------------------\n"
                    
                    for i, item in enumerate(new_analysis_data[:20], 1):
                        ticker = item.get('ticker', 'N/A')
                        score = item.get('quality_score', 0)
                        market_cap = item.get('market_cap', 'N/A')
                        tier = item.get('tier', 'Unknown')
                        red_flags = item.get('red_flags', 0)
                        
                        line = f"{i:<4} {ticker:<8} ${market_cap:<12} {score:<8.1f}    {tier:<12} {red_flags:<10}"
                        merged_content += line + '\n'
            
            # Write updated content
            with open(self.summary_file, 'w') as f:
                f.write(merged_content)
            
            logger.info(f"Updated summary file with {len(new_analysis_data)} new analysis results")
            
        except Exception as e:
            logger.error(f"Error updating summary incrementally: {e}")
            raise
    
    def get_archive_info(self) -> Dict:
        """
        Get information about archived summaries.
        
        Returns:
            Dictionary with archive information
        """
        archives = []
        current_quarter = self.get_current_quarter()
        
        for archive_file in sorted(self.archive_dir.glob("quality_analysis_summary_Q*.txt")):
            # Extract quarter from filename
            match = re.search(r'Q(\d{5})', archive_file.name)
            if match:
                archive_quarter = int(match.group(1))
                year = archive_quarter // 10
                quarter = archive_quarter % 10
                
                quarters_old = current_quarter - archive_quarter
                
                archives.append({
                    'filename': archive_file.name,
                    'path': str(archive_file),
                    'quarter': archive_quarter,
                    'year': year,
                    'quarter_num': quarter,
                    'quarters_old': quarters_old,
                    'size_bytes': archive_file.stat().st_size,
                    'modified': datetime.fromtimestamp(archive_file.stat().st_mtime).isoformat()
                })
        
        return {
            'total_archives': len(archives),
            'oldest_archive': archives[0] if archives else None,
            'newest_archive': archives[-1] if archives else None,
            'archives': archives,
            'max_quarters': self.MAX_QUARTERS_ARCHIVE
        }
    
    def validate_summary_integrity(self) -> Dict:
        """
        Validate the integrity of the current summary file.
        
        Returns:
            Dictionary with validation results
        """
        result = {
            'exists': False,
            'has_header': False,
            'has_top_stocks': False,
            'has_distributions': False,
            'quarter_current': True,
            'ticker_count': 0,
            'errors': []
        }
        
        if not self.summary_file.exists():
            result['errors'].append("Summary file does not exist")
            return result
        
        result['exists'] = True
        
        try:
            with open(self.summary_file, 'r') as f:
                content = f.read()
            
            # Check for required sections
            if 'QUALITY ANALYSIS SUMMARY' in content:
                result['has_header'] = True
            
            if 'TOP 20 STOCKS BY QUALITY SCORE:' in content:
                result['has_top_stocks'] = True
            
            if any(section in content for section in ['MARKET CAP DISTRIBUTION:', 'ROE PERSISTENCE SUMMARY:']):
                result['has_distributions'] = True
            
            # Check quarter currency
            current_quarter = self.get_current_quarter()
            summary_quarter = self.parse_quarter_from_summary(content)
            
            if summary_quarter and summary_quarter < current_quarter:
                result['quarter_current'] = False
                result['errors'].append(f"Summary is from quarter {summary_quarter}, current is {current_quarter}")
            
            # Count unique tickers
            tickers = self.extract_existing_tickers(content)
            result['ticker_count'] = len(tickers)
            
        except Exception as e:
            result['errors'].append(f"Error reading summary file: {e}")
        
        return result