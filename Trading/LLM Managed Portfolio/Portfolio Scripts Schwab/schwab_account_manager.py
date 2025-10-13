"""
Schwab Account Manager Module
Handles account data synchronization between Schwab API and local portfolio state
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchwabAccountManager:
    """
    Manages synchronization between Schwab account data and local portfolio state
    Retrieves real-time positions, balances, and account information
    """

    def __init__(self, schwab_client, portfolio_manager):
        """
        Initialize account manager with Schwab client and portfolio manager

        Args:
            schwab_client: Authenticated schwab-py client instance
            portfolio_manager: PortfolioManager instance for local state management
        """
        self.client = schwab_client
        self.portfolio = portfolio_manager
        self.account_hash = None
        self.account_number = None
        self.linked_accounts = []

        logger.info("✅ Schwab Account Manager initialized")

    def discover_accounts(self) -> List[Dict]:
        """
        Discover all linked Schwab accounts

        Returns:
            List of account information dictionaries
        """
        try:
            logger.info("🔍 Discovering linked Schwab accounts...")

            response = self.client.get_account_numbers()
            if response.status_code == 200:
                accounts_data = response.json()

                # Parse account numbers and hashes
                self.linked_accounts = []
                for account in accounts_data:
                    account_info = {
                        'account_number': account.get('accountNumber'),
                        'hash_value': account.get('hashValue'),
                        'account_type': account.get('accountType', 'Unknown')
                    }
                    self.linked_accounts.append(account_info)
                    logger.info(f"   📊 Found account: {account_info['account_type']} (...{account_info['account_number'][-4:]})")

                # Set primary account (first one by default)
                if self.linked_accounts:
                    self.account_hash = self.linked_accounts[0]['hash_value']
                    self.account_number = self.linked_accounts[0]['account_number']
                    logger.info(f"✅ Primary account set: ...{self.account_number[-4:]}")

                return self.linked_accounts
            else:
                logger.error(f"❌ Failed to retrieve accounts: HTTP {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"❌ Error discovering accounts: {e}")
            return []

    def set_primary_account(self, account_index: int = 0):
        """
        Set the primary account to use for trading and sync

        Args:
            account_index: Index in linked_accounts list (default: 0)
        """
        if not self.linked_accounts:
            logger.error("❌ No linked accounts found. Run discover_accounts() first.")
            return False

        if account_index >= len(self.linked_accounts):
            logger.error(f"❌ Invalid account index {account_index}. Only {len(self.linked_accounts)} accounts available.")
            return False

        account = self.linked_accounts[account_index]
        self.account_hash = account['hash_value']
        self.account_number = account['account_number']
        logger.info(f"✅ Primary account changed to: ...{self.account_number[-4:]}")
        return True

    def fetch_account_data(self, account_hash: str = None) -> Optional[Dict]:
        """
        Fetch complete account data from Schwab API

        Args:
            account_hash: Specific account hash (uses primary if not specified)

        Returns:
            Dict containing account data or None if failed
        """
        try:
            if account_hash is None:
                account_hash = self.account_hash

            if not account_hash:
                logger.error("❌ No account hash available. Run discover_accounts() first.")
                return None

            logger.info(f"📡 Fetching account data from Schwab...")

            response = self.client.get_account(
                account_hash,
                fields=['positions']  # Request position details
            )

            if response.status_code == 200:
                account_data = response.json()
                logger.info("✅ Successfully retrieved account data from Schwab")
                return account_data
            else:
                logger.error(f"❌ Failed to fetch account data: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"❌ Error fetching account data: {e}")
            return None

    def parse_account_positions(self, account_data: Dict) -> Tuple[Dict, float]:
        """
        Parse positions and cash from Schwab account data

        Args:
            account_data: Raw account data from Schwab API

        Returns:
            Tuple of (positions_dict, cash_balance)
        """
        try:
            positions = {}
            cash_balance = 0.0

            # Navigate Schwab API response structure
            # Typical structure: account_data -> securitiesAccount -> positions
            securities_account = account_data.get('securitiesAccount', {})

            # Extract cash balance
            current_balances = securities_account.get('currentBalances', {})
            cash_balance = float(current_balances.get('cashBalance', 0.0))

            # Alternative cash fields
            if cash_balance == 0.0:
                cash_balance = float(current_balances.get('availableFunds', 0.0))
            if cash_balance == 0.0:
                cash_balance = float(current_balances.get('cashAvailableForTrading', 0.0))

            logger.info(f"💰 Cash balance: ${cash_balance:.2f}")

            # Extract positions
            positions_list = securities_account.get('positions', [])

            if not positions_list:
                logger.warning("⚠️  No positions found in account")
                return positions, cash_balance

            logger.info(f"📊 Processing {len(positions_list)} positions...")

            for position_data in positions_list:
                try:
                    # Extract instrument details
                    instrument = position_data.get('instrument', {})
                    ticker = instrument.get('symbol', '').upper()

                    # Only process equity positions (skip options, etc.)
                    asset_type = instrument.get('assetType', '')
                    if asset_type != 'EQUITY':
                        logger.debug(f"   ⏭️  Skipping non-equity: {ticker} ({asset_type})")
                        continue

                    # Extract position details
                    shares = float(position_data.get('longQuantity', 0))

                    # Average price might be in different fields
                    entry_price = float(position_data.get('averagePrice', 0))
                    if entry_price == 0:
                        entry_price = float(position_data.get('settledLongQuantity', 0))

                    # Current market value
                    market_value = float(position_data.get('marketValue', shares * entry_price))

                    if shares > 0 and ticker:
                        positions[ticker] = {
                            'shares': int(shares),
                            'entry_price': entry_price,
                            'allocation': market_value
                        }
                        logger.info(f"   ✅ {ticker}: {int(shares)} shares @ ${entry_price:.2f} (${market_value:.2f})")

                except Exception as e:
                    logger.warning(f"   ⚠️  Error parsing position: {e}")
                    continue

            logger.info(f"✅ Parsed {len(positions)} equity positions")
            return positions, cash_balance

        except Exception as e:
            logger.error(f"❌ Error parsing account positions: {e}")
            return {}, 0.0

    def sync_to_local_portfolio(self, account_data: Dict = None) -> bool:
        """
        Sync Schwab account data to local portfolio state

        Args:
            account_data: Pre-fetched account data (will fetch if not provided)

        Returns:
            True if sync successful, False otherwise
        """
        try:
            print("\n" + "=" * 60)
            print("🔄 SYNCING SCHWAB ACCOUNT TO LOCAL PORTFOLIO")
            print("=" * 60)

            # Fetch account data if not provided
            if account_data is None:
                account_data = self.fetch_account_data()

            if not account_data:
                print("❌ Failed to fetch account data for sync")
                return False

            # Parse positions and cash
            schwab_positions, schwab_cash = self.parse_account_positions(account_data)

            if not schwab_positions and schwab_cash == 0:
                print("⚠️  No positions or cash found in Schwab account")
                return False

            # Show comparison before sync
            print("\n📊 COMPARISON: Local vs Schwab Account")
            print("-" * 60)
            print(f"{'Ticker':<10} {'Local Shares':<15} {'Schwab Shares':<15} {'Status':<10}")
            print("-" * 60)

            # Compare positions
            all_tickers = set(list(self.portfolio.holdings.keys()) + list(schwab_positions.keys()))

            differences_found = False
            for ticker in sorted(all_tickers):
                local_shares = self.portfolio.holdings.get(ticker, {}).get('shares', 0)
                schwab_shares = schwab_positions.get(ticker, {}).get('shares', 0)

                if local_shares != schwab_shares:
                    status = "⚠️ DIFF"
                    differences_found = True
                else:
                    status = "✅ MATCH"

                print(f"{ticker:<10} {local_shares:<15} {schwab_shares:<15} {status:<10}")

            # Compare cash
            print("-" * 60)
            print(f"{'Cash':<10} ${self.portfolio.cash:<14.2f} ${schwab_cash:<14.2f} {'⚠️ DIFF' if abs(self.portfolio.cash - schwab_cash) > 0.01 else '✅ MATCH'}")
            print("-" * 60)

            if not differences_found and abs(self.portfolio.cash - schwab_cash) < 0.01:
                print("\n✅ Local portfolio already matches Schwab account - no sync needed")
                return True

            # Perform sync
            print("\n🔄 Updating local portfolio to match Schwab account...")

            # Update positions
            self.portfolio.holdings = schwab_positions.copy()

            # Update cash
            self.portfolio.cash = schwab_cash

            # Save updated state
            success = self.portfolio.save_portfolio_state()

            if success:
                print("\n✅ SYNC COMPLETED SUCCESSFULLY")
                print(f"   Positions: {len(schwab_positions)}")
                print(f"   Cash: ${schwab_cash:.2f}")
                print(f"   Total value: ${sum(p['allocation'] for p in schwab_positions.values()) + schwab_cash:.2f}")
                return True
            else:
                print("\n❌ Failed to save portfolio state after sync")
                return False

        except Exception as e:
            logger.error(f"❌ Error during sync: {e}")
            print(f"\n❌ Sync failed: {e}")
            return False

    def get_account_summary(self, account_data: Dict = None) -> Dict:
        """
        Generate comprehensive account summary

        Args:
            account_data: Pre-fetched account data (will fetch if not provided)

        Returns:
            Dict with account summary information
        """
        try:
            if account_data is None:
                account_data = self.fetch_account_data()

            if not account_data:
                return {'error': 'Failed to fetch account data'}

            securities_account = account_data.get('securitiesAccount', {})
            current_balances = securities_account.get('currentBalances', {})

            # Parse positions
            positions, cash = self.parse_account_positions(account_data)

            # Calculate totals
            positions_value = sum(p['allocation'] for p in positions.values())
            total_value = positions_value + cash

            summary = {
                'account_number': f"...{self.account_number[-4:]}" if self.account_number else "Unknown",
                'account_type': securities_account.get('type', 'Unknown'),
                'timestamp': datetime.now().isoformat(),
                'cash': cash,
                'positions_value': positions_value,
                'total_value': total_value,
                'positions_count': len(positions),
                'positions': positions,
                'balances': {
                    'available_funds': float(current_balances.get('availableFunds', 0)),
                    'buying_power': float(current_balances.get('buyingPower', 0)),
                    'cash_balance': cash,
                    'equity': float(current_balances.get('equity', 0))
                }
            }

            return summary

        except Exception as e:
            logger.error(f"❌ Error generating account summary: {e}")
            return {'error': str(e)}

    def print_account_summary(self, summary: Dict = None):
        """
        Print formatted account summary to console

        Args:
            summary: Pre-generated summary (will generate if not provided)
        """
        try:
            if summary is None:
                summary = self.get_account_summary()

            if 'error' in summary:
                print(f"❌ Error: {summary['error']}")
                return

            print("\n" + "=" * 60)
            print("📊 SCHWAB ACCOUNT SUMMARY")
            print("=" * 60)
            print(f"Account: {summary['account_number']} ({summary['account_type']})")
            print(f"Timestamp: {summary['timestamp']}")
            print("-" * 60)
            print(f"💰 Cash:             ${summary['cash']:>15,.2f}")
            print(f"📈 Positions Value:  ${summary['positions_value']:>15,.2f}")
            print(f"💎 Total Value:      ${summary['total_value']:>15,.2f}")
            print("-" * 60)
            print(f"Positions: {summary['positions_count']}")
            print("-" * 60)

            if summary['positions']:
                print(f"\n{'Ticker':<10} {'Shares':<10} {'Entry Price':<15} {'Value':<15}")
                print("-" * 60)
                for ticker, pos in sorted(summary['positions'].items()):
                    print(f"{ticker:<10} {pos['shares']:<10} ${pos['entry_price']:<14.2f} ${pos['allocation']:<14.2f}")

            print("\n" + "=" * 60)
            print(f"💵 Available Funds:  ${summary['balances']['available_funds']:>15,.2f}")
            print(f"💪 Buying Power:     ${summary['balances']['buying_power']:>15,.2f}")
            print("=" * 60)

        except Exception as e:
            logger.error(f"❌ Error printing account summary: {e}")
            print(f"❌ Error displaying summary: {e}")

    def get_transaction_history(self, start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """
        Retrieve transaction history from Schwab account

        Args:
            start_date: Start date for history (default: 30 days ago)
            end_date: End date for history (default: today)

        Returns:
            List of transaction dictionaries
        """
        try:
            if not self.account_hash:
                logger.error("❌ No account hash available. Run discover_accounts() first.")
                return []

            # Default to last 30 days if dates not provided
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                start_date = end_date - pd.Timedelta(days=30)

            logger.info(f"📜 Fetching transaction history from {start_date.date()} to {end_date.date()}...")

            response = self.client.get_transactions(
                self.account_hash,
                start_datetime=start_date,
                end_datetime=end_date
            )

            if response.status_code == 200:
                transactions = response.json()
                logger.info(f"✅ Retrieved {len(transactions)} transactions")
                return transactions
            else:
                logger.error(f"❌ Failed to fetch transactions: HTTP {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"❌ Error fetching transaction history: {e}")
            return []
