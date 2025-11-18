# LLM Managed Portfolio - Claude Instructions

## 🎯 Primary Goal
Achieve the quality investing framework defined in `Portfolio Scripts Schwab/docs/research/quality_investing_thresholds_research.md` by systematically executing the STEPS methodology to generate trading recommendations.

## 📋 Output Format
All trading recommendations must be formatted according to `trading_template.md` with:
- Clear BUY/SELL/HOLD decisions
- Quality scores and thematic scores
- Position sizing with risk parameters
- Reasoning based on STEPS framework

## 🚀 Core Workflow
1. **Run STEPS Analysis**: `python "Portfolio Scripts Schwab/analysis/steps_orchestrator.py"`
2. **Review Output**: Check `trading_recommendations/trading_recommendations_YYYYMMDD.md`
3. **Manual Approval**: Edit `manual_trades_override.json` with approved trades
4. **Execute**: `python "Portfolio Scripts Schwab/main.py"` (market hours only)

## 📁 Working Directory
**PRIMARY**: `Portfolio Scripts Schwab/` - Fully modular Schwab API system
**Environment**: `conda activate trading_env` (Python 3.11+)
**main.py** is the main file but lives outside the primary folder

## 📝 Change Management
- **Update**: `CHANGELOG.md` for all significant changes
- **Commit**: Regularly push changes to GitHub with descriptive messages
- **Document**: Update appropriate docs in `Portfolio Scripts Schwab/docs/` as needed

## 📚 Detailed Documentation
All comprehensive guides are in `Portfolio Scripts Schwab/docs/`:
- **Quick Start**: `docs/guides/QUICK_START.md` - How to run scripts
- **Setup**: `docs/guides/ENVIRONMENT_SETUP.md` - Environment configuration
- **Architecture**: `docs/guides/SYSTEM_ARCHITECTURE.md` - System design
- **STEPS**: `docs/guides/STEPS_METHODOLOGY.md` - 10-step framework
- **Research**: `docs/research/` - Investment frameworks and methodology

## 🔑 Key Principles
- All trades require manual approval (human-in-the-loop)
- Quality score ≥70 for core holdings, Thematic score ≥28 for opportunistic
- Maintain 4-tier allocation: Large Cap (65-70%), Mid Cap (15-20%), Small Cap (10-15%), Thematic (5-10%)
- Trading operations require market hours (Mon-Fri 9:30AM-4PM ET)
- Read-only operations (reports, analysis) available 24/7
