#!/usr/bin/env python3
"""
User Agent Service Runner

Scrapes, tests, and updates user agents in the database.
"""

import sys
import os
from datetime import datetime, timezone

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.connection import SessionLocal
from src.scrapers.user_agents.service import UserAgentService
from src.scrapers.user_agents.models import UserAgent


def get_stats(session):
    """Get current database statistics"""
    all_uas = session.query(UserAgent).all()
    stats = {
        'total': len(all_uas),
        'working': len([ua for ua in all_uas if ua.status == 'working']),
        'failing': len([ua for ua in all_uas if ua.status == 'failing']),
        'unknown': len([ua for ua in all_uas if ua.status == 'unknown']),
        'retired': len([ua for ua in all_uas if ua.status == 'retired'])
    }
    return stats


def test_user_agents(ua_service, status='unknown', limit=20):
    """Test user agents with given status"""
    session = ua_service.session
    uas = session.query(UserAgent).filter(UserAgent.status == status).limit(limit).all()
    
    if not uas:
        return 0, 0
    
    working = 0
    failing = 0
    
    for ua in uas:
        try:
            is_working = ua_service.test_user_agent(ua.user_agent)
            ua_service.update_user_agent_status(ua.user_agent, is_working)
            
            if is_working:
                working += 1
            else:
                failing += 1
        except Exception:
            failing += 1
    
    return working, failing


def main():
    """Main function to run the user agent service"""
    print(f"User Agent Service - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    session = SessionLocal()
    ua_service = UserAgentService(session)
    
    try:
        # Show initial stats
        initial_stats = get_stats(session)
        print(f"Initial: {initial_stats['total']} total, {initial_stats['working']} working, {initial_stats['unknown']} unknown")
        
        # Scrape and import new user agents
        print("Scraping new user agents...")
        new_uas = ua_service.scrape_new_user_agents()
        if new_uas:
            ua_service.import_user_agents(new_uas)
            print(f"Imported {len(new_uas)} new user agents")
        
        # Test all user agents regardless of status
        print("Testing all user agents...")
        all_working, all_failing = ua_service.test_all_user_agents(50)
        print(f"All agents tested: {all_working} working, {all_failing} failing")
        
        # Clean up old user agents
        removed_count = ua_service.cleanup_old_user_agents(days_old=30)
        if removed_count > 0:
            print(f"Removed {removed_count} old user agents")
        
        # Show final stats
        final_stats = get_stats(session)
        print(f"Final: {final_stats['total']} total, {final_stats['working']} working")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        session.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
