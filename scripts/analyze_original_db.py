#!/usr/bin/env python3
"""
Database Structure Analyzer for Original lovelush Database
Analyze existing agents and subaccounts data structure in lovelush database
"""

import os
import sys
import json
from typing import Dict, List, Optional
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymongo
from pymongo import MongoClient
from bson import ObjectId


class OriginalDatabaseAnalyzer:
    """Analyze original database structure for agents and subaccounts"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017"):
        self.mongo_uri = mongo_uri
        self.client = MongoClient(mongo_uri)
        self.lovelush_db = self.client["lovelush"]  # 原数据库
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
    
    def _convert_objectid_to_string(self, obj):
        """Convert ObjectId instances to strings for JSON serialization"""
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, dict):
            return {key: self._convert_objectid_to_string(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_objectid_to_string(item) for item in obj]
        else:
            return obj
    
    def analyze_collection_structure(self, collection_name: str) -> Dict:
        """
        Analyze the structure of a collection in lovelush database
        
        Args:
            collection_name: Collection name (agents or subaccounts)
            
        Returns:
            Dict: Analysis results including sample documents and field structure
        """
        try:
            collection = self.lovelush_db[collection_name]
            
            # Get collection stats
            total_docs = collection.count_documents({})
            
            print(f"\n📊 Collection: lovelush.{collection_name}")
            print(f"Total documents: {total_docs}")
            
            if total_docs == 0:
                print("⚠️ Collection is empty")
                return {"total_docs": 0, "sample_docs": [], "fields": {}}
            
            # Get sample documents (up to 3)
            sample_docs = list(collection.find().limit(3))
            
            # Analyze field structure from all documents
            all_fields = set()
            field_types = {}
            
            for doc in collection.find():
                for key, value in doc.items():
                    all_fields.add(key)
                    
                    # Track field types
                    field_type = type(value).__name__
                    if key not in field_types:
                        field_types[key] = set()
                    field_types[key].add(field_type)
            
            print(f"Unique fields: {len(all_fields)}")
            print("Field types:")
            for field, types in sorted(field_types.items()):
                print(f"  - {field}: {', '.join(sorted(types))}")
            
            # Print sample documents (pretty formatted)
            print("\nSample documents:")
            for i, doc in enumerate(sample_docs, 1):
                print(f"\n--- Sample {i} ---")
                # Convert ObjectId to string for JSON serialization
                doc_copy = self._convert_objectid_to_string(doc)
                print(json.dumps(doc_copy, indent=2, default=str, ensure_ascii=False))
            
            return {
                "total_docs": total_docs,
                "sample_docs": sample_docs,
                "fields": dict(field_types),
                "all_fields": list(all_fields)
            }
            
        except Exception as e:
            print(f"❌ Error analyzing collection lovelush.{collection_name}: {str(e)}")
            return {"error": str(e)}
    
    def list_all_collections(self):
        """List all collections in lovelush database"""
        try:
            collections = self.lovelush_db.list_collection_names()
            print(f"\n📋 All collections in lovelush database:")
            for collection in collections:
                count = self.lovelush_db[collection].count_documents({})
                print(f"  - {collection}: {count} documents")
            return collections
        except Exception as e:
            print(f"❌ Error listing collections: {str(e)}")
            return []
    
    def analyze_agents_and_subaccounts(self):
        """Analyze agents and subaccounts in lovelush database"""
        print("🔍 Analyzing original lovelush database structures...")
        print("=" * 60)
        
        # First list all collections
        all_collections = self.list_all_collections()
        
        # Check if agents and subaccounts exist
        target_collections = ["agents", "sub_accounts"]  # 注意这里是sub_accounts，不是subaccounts
        existing_collections = [col for col in target_collections if col in all_collections]
        
        if not existing_collections:
            print("\n⚠️ Neither 'agents' nor 'subaccounts' collections found!")
            print("Available collections:", all_collections)
            return {}
        
        analysis_results = {}
        
        for collection_name in existing_collections:
            print(f"\n🏛️ Analyzing {collection_name}...")
            print("-" * 40)
            
            try:
                result = self.analyze_collection_structure(collection_name)
                analysis_results[collection_name] = result
            except Exception as e:
                print(f"❌ Error with {collection_name}: {str(e)}")
                analysis_results[collection_name] = {"error": str(e)}
        
        return analysis_results


def main():
    """Main analysis function"""
    print("🚀 Starting original database (lovelush) structure analysis")
    print("=" * 60)
    
    with OriginalDatabaseAnalyzer() as analyzer:
        # Analyze agents and subaccounts
        analysis_results = analyzer.analyze_agents_and_subaccounts()
    
    print("\n" + "=" * 60)
    print("Analysis completed.")


if __name__ == "__main__":
    main()