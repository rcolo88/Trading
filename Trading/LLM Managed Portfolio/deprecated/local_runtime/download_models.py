#!/usr/bin/env python3
"""
Model Download and Setup Script for Local LLM Trading System
Downloads and caches the 4 specialized financial models for offline use

This script:
1. Downloads models from HuggingFace Hub
2. Stores them in local cache for offline access
3. Validates model integrity and availability
4. Provides disk usage estimates and management
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import shutil

try:
    from transformers import AutoTokenizer, AutoModel
    from huggingface_hub import snapshot_download, hf_hub_download
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("❌ Required dependencies not found. Please install:")
    print("pip install transformers huggingface_hub torch")

# Model configurations from local_llm_server
MODEL_CONFIGS = {
    "news_analysis": {
        "model_id": "AdaptLLM/Llama-3-FinMA-8B-Instruct",
        "purpose": "Financial news analysis and sentiment extraction",
        "estimated_size": "16GB",
        "quantization": "8bit",
    },
    
    "market_analysis": {
        "model_id": "Qwen/Qwen2.5-14B-Instruct",
        "purpose": "Technical analysis and market pattern recognition",
        "estimated_size": "28GB",
        "quantization": "4bit",
    },
    
    "trading_decision": {
        "model_id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "purpose": "Trading strategy and position management",
        "estimated_size": "28GB",
        "quantization": "4bit",
    },
    
    "risk_validation": {
        "model_id": "microsoft/Phi-3-medium-4k-instruct",
        "purpose": "Fast risk checks and compliance",
        "estimated_size": "8GB",
        "quantization": "8bit",
    }
}


class ModelDownloader:
    """Manages downloading and caching of LLM models"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize model downloader
        
        Args:
            cache_dir: Custom cache directory (default: ~/.cache/huggingface)
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".cache" / "huggingface"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🗂️  Model cache directory: {self.cache_dir}")
        print(f"📊 Available disk space: {self._get_available_space():.1f}GB")
        
    def _get_available_space(self) -> float:
        """Get available disk space in GB"""
        try:
            statvfs = os.statvfs(self.cache_dir)
            return (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
        except:
            return 0.0
    
    def _get_directory_size(self, path: Path) -> float:
        """Get directory size in GB"""
        try:
            total = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
            return total / (1024**3)
        except:
            return 0.0
    
    def check_model_status(self, model_name: str) -> Dict[str, any]:
        """Check if model is already downloaded and cached"""
        
        config = MODEL_CONFIGS.get(model_name)
        if not config:
            return {"exists": False, "error": f"Unknown model: {model_name}"}
        
        model_id = config["model_id"]
        model_path = self.cache_dir / "models--" / model_id.replace("/", "--")
        
        status = {
            "model_name": model_name,
            "model_id": model_id,
            "exists": model_path.exists(),
            "path": str(model_path),
            "estimated_size": config["estimated_size"],
            "purpose": config["purpose"]
        }
        
        if model_path.exists():
            actual_size = self._get_directory_size(model_path)
            status["actual_size"] = f"{actual_size:.1f}GB"
            status["complete"] = actual_size > 0.1  # Basic completeness check
        else:
            status["actual_size"] = "0GB"
            status["complete"] = False
            
        return status
    
    def check_all_models(self) -> Dict[str, Dict]:
        """Check status of all models"""
        
        print("🔍 Checking model status...")
        print("=" * 60)
        
        statuses = {}
        total_size = 0
        downloaded_count = 0
        
        for model_name in MODEL_CONFIGS.keys():
            status = self.check_model_status(model_name)
            statuses[model_name] = status
            
            # Display status
            status_icon = "✅" if status.get("complete") else "❌"
            size_display = status.get("actual_size", "0GB")
            
            print(f"{status_icon} {model_name}:")
            print(f"   Model: {status['model_id']}")
            print(f"   Size: {size_display} (est. {status['estimated_size']})")
            print(f"   Purpose: {status['purpose']}")
            print()
            
            if status.get("complete"):
                downloaded_count += 1
                # Parse actual size for total
                try:
                    actual_gb = float(status["actual_size"].replace("GB", ""))
                    total_size += actual_gb
                except:
                    pass
        
        print(f"📊 Summary: {downloaded_count}/{len(MODEL_CONFIGS)} models ready")
        print(f"💾 Total downloaded: {total_size:.1f}GB")
        print(f"💿 Available space: {self._get_available_space():.1f}GB")
        
        return statuses
    
    def download_model(self, model_name: str, force_redownload: bool = False) -> bool:
        """Download a specific model"""
        
        if not TRANSFORMERS_AVAILABLE:
            print("❌ Cannot download models - transformers not available")
            return False
        
        config = MODEL_CONFIGS.get(model_name)
        if not config:
            print(f"❌ Unknown model: {model_name}")
            return False
        
        model_id = config["model_id"]
        estimated_size = config["estimated_size"]
        
        print(f"📥 Downloading {model_name}...")
        print(f"   Model ID: {model_id}")
        print(f"   Estimated size: {estimated_size}")
        print(f"   Purpose: {config['purpose']}")
        print()
        
        # Check available space
        estimated_gb = float(estimated_size.replace("GB", ""))
        available_gb = self._get_available_space()
        
        if available_gb < estimated_gb * 1.2:  # 20% buffer
            print(f"⚠️  Warning: Low disk space!")
            print(f"   Available: {available_gb:.1f}GB")
            print(f"   Required: {estimated_gb:.1f}GB (+ 20% buffer)")
            
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("❌ Download cancelled")
                return False
        
        try:
            print("🔄 Downloading model files...")
            
            # Download model using HuggingFace Hub
            local_dir = snapshot_download(
                repo_id=model_id,
                cache_dir=str(self.cache_dir),
                resume_download=True,
                local_files_only=False
            )
            
            print(f"✅ Successfully downloaded {model_name}")
            print(f"   Location: {local_dir}")
            
            # Verify download
            status = self.check_model_status(model_name)
            if status.get("complete"):
                print(f"✅ Model verification passed: {status['actual_size']}")
                return True
            else:
                print("⚠️  Model verification failed - download may be incomplete")
                return False
                
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    
    def download_all_models(self, force_redownload: bool = False) -> Dict[str, bool]:
        """Download all models"""
        
        print("🚀 Starting bulk model download...")
        print("=" * 60)
        
        # Calculate total estimated size
        total_estimated = 0
        for config in MODEL_CONFIGS.values():
            size_str = config["estimated_size"]
            size_gb = float(size_str.replace("GB", ""))
            total_estimated += size_gb
        
        available_space = self._get_available_space()
        print(f"📊 Download Summary:")
        print(f"   Total estimated size: {total_estimated:.1f}GB")
        print(f"   Available disk space: {available_space:.1f}GB")
        print(f"   Models to download: {len(MODEL_CONFIGS)}")
        print()
        
        if available_space < total_estimated * 1.2:
            print("⚠️  WARNING: Insufficient disk space!")
            print("   Consider downloading models individually or freeing up space")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print("❌ Bulk download cancelled")
                return {}
        
        results = {}
        
        for model_name in MODEL_CONFIGS.keys():
            print(f"\n{'='*20} {model_name} {'='*20}")
            
            # Check if already downloaded
            if not force_redownload:
                status = self.check_model_status(model_name)
                if status.get("complete"):
                    print(f"✅ {model_name} already downloaded, skipping...")
                    results[model_name] = True
                    continue
            
            # Download model
            success = self.download_model(model_name, force_redownload)
            results[model_name] = success
            
            if not success:
                print(f"❌ Failed to download {model_name}")
                response = input("Continue with remaining models? (Y/n): ")
                if response.lower() == 'n':
                    break
        
        # Final summary
        print("\n" + "="*60)
        print("📊 DOWNLOAD SUMMARY")
        print("="*60)
        
        successful = sum(1 for success in results.values() if success)
        total = len(results)
        
        for model_name, success in results.items():
            status_icon = "✅" if success else "❌"
            print(f"{status_icon} {model_name}")
        
        print(f"\n🎯 Results: {successful}/{total} models downloaded successfully")
        
        if successful == total:
            print("🎉 All models ready! You can now run:")
            print("   python main_local.py --test-components")
        else:
            print("⚠️  Some downloads failed. Check errors above and retry if needed.")
        
        return results
    
    def clean_cache(self, model_name: Optional[str] = None) -> bool:
        """Clean model cache"""
        
        if model_name:
            # Clean specific model
            config = MODEL_CONFIGS.get(model_name)
            if not config:
                print(f"❌ Unknown model: {model_name}")
                return False
            
            model_id = config["model_id"]
            model_path = self.cache_dir / "models--" / model_id.replace("/", "--")
            
            if model_path.exists():
                size_before = self._get_directory_size(model_path)
                shutil.rmtree(model_path)
                print(f"✅ Removed {model_name} ({size_before:.1f}GB freed)")
                return True
            else:
                print(f"ℹ️  {model_name} not found in cache")
                return False
        else:
            # Clean all models
            print("🗑️  Cleaning all model cache...")
            total_freed = 0
            
            for model_name in MODEL_CONFIGS.keys():
                config = MODEL_CONFIGS[model_name]
                model_id = config["model_id"]
                model_path = self.cache_dir / "models--" / model_id.replace("/", "--")
                
                if model_path.exists():
                    size = self._get_directory_size(model_path)
                    shutil.rmtree(model_path)
                    total_freed += size
                    print(f"✅ Removed {model_name} ({size:.1f}GB)")
            
            print(f"🎯 Total space freed: {total_freed:.1f}GB")
            return total_freed > 0


def main():
    """Main entry point for model download script"""
    
    parser = argparse.ArgumentParser(description='Download and manage LLM models for local trading system')
    parser.add_argument('--check', action='store_true', 
                       help='Check status of all models')
    parser.add_argument('--download', metavar='MODEL', 
                       help='Download specific model (or "all" for all models)')
    parser.add_argument('--clean', metavar='MODEL', nargs='?', const='all',
                       help='Clean model cache (specific model or all)')
    parser.add_argument('--force', action='store_true',
                       help='Force redownload even if model exists')
    parser.add_argument('--cache-dir', metavar='PATH',
                       help='Custom cache directory path')
    
    args = parser.parse_args()
    
    if not TRANSFORMERS_AVAILABLE:
        print("❌ Required dependencies not installed")
        print("Please run: pip install transformers huggingface_hub torch")
        sys.exit(1)
    
    # Initialize downloader
    downloader = ModelDownloader(cache_dir=args.cache_dir)
    
    if args.check:
        # Check model status
        downloader.check_all_models()
        
    elif args.download:
        # Download models
        if args.download.lower() == 'all':
            downloader.download_all_models(force_redownload=args.force)
        else:
            downloader.download_model(args.download, force_redownload=args.force)
            
    elif args.clean is not None:
        # Clean cache
        if args.clean == 'all':
            downloader.clean_cache()
        else:
            downloader.clean_cache(args.clean)
            
    else:
        # Default: show status and usage
        print("🤖 Local LLM Trading System - Model Manager")
        print("=" * 50)
        
        # Show current status
        downloader.check_all_models()
        
        print("\n💡 Usage Examples:")
        print("   python download_models.py --check                    # Check model status")
        print("   python download_models.py --download all             # Download all models")  
        print("   python download_models.py --download risk_validation # Download specific model")
        print("   python download_models.py --clean all                # Clean all cached models")
        print("   python download_models.py --clean news_analysis      # Clean specific model")
        print()
        
        # Check if any models are ready
        statuses = downloader.check_all_models()
        ready_models = sum(1 for s in statuses.values() if s.get("complete"))
        
        if ready_models == 0:
            print("🚀 To get started, download models:")
            print("   python download_models.py --download all")
        elif ready_models < len(MODEL_CONFIGS):
            print("⚠️  Some models missing. Download remaining models:")
            print("   python download_models.py --download all")
        else:
            print("✅ All models ready! Test the system:")
            print("   python main_local.py --test-components --force-cpu")


if __name__ == "__main__":
    main()