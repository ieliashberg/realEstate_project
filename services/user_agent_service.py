"""
User Agent Service

Provides database-backed user agent management with:
- Automatic testing and validation
- Lifecycle management (working -> failing -> retired)
- Fallback to default user agents
- Scraping and importing new user agents
"""

import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from bs4 import BeautifulSoup

from models.user_agent import UserAgent

class UserAgentService:
    """Service for managing user agents with database persistence"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_working_user_agents(self, count: int = 15) -> List[str]:
        """
        Get a list of working user agents from the database.
        Returns empty list if none are found (database-driven only).
        """
        # Get working user agents from database
        working_uas = self.session.query(UserAgent).filter(
            and_(
                UserAgent.status == 'working',
                UserAgent.last_tested > datetime.now(timezone.utc) - timedelta(hours=24)
            )
        ).limit(count * 2).all()
        
        if working_uas:
            # Return random selection of working UAs
            selected = random.sample(working_uas, min(count, len(working_uas)))
            return [ua.user_agent for ua in selected]
        
        # No fallback - return empty list if no working user agents
        return []
    
    def test_user_agent(self, user_agent: str, test_url: str = None) -> bool:
        """
        Test if a user agent is currently working.
        Returns True if successful, False otherwise.
        """
        if test_url is None:
            test_url = "https://www.zillow.com/rental-manager/price-my-rental/results/1169-sesame-dr-sunnyvale-ca-94087/"
        
        try:
            from utils.http_utils import make_request
            headers = {"User-Agent": user_agent}
            response = make_request(test_url, headers=headers, timeout=10)
            # httpbin.org/user-agent returns JSON with the user agent, so we can verify it
            if response and len(response) > 50:
                import json
                try:
                    data = json.loads(response)
                    # Check if the returned user agent matches what we sent
                    returned_ua = data.get('user-agent', '')
                    return returned_ua == user_agent
                except json.JSONDecodeError:
                    # If not JSON, just check if we got a reasonable response
                    return True
            return False
        except Exception:
            return False
    
    def update_user_agent_status(self, user_agent_str: str, is_working: bool):
        """Update the status of a user agent based on test results"""
        ua = self.session.query(UserAgent).filter(UserAgent.user_agent == user_agent_str).first()
        
        if not ua:
            # Create new user agent record
            ua = UserAgent(
                user_agent=user_agent_str,
                status='working' if is_working else 'failing',
                fail_count=0 if is_working else 1,
                last_tested=datetime.now(timezone.utc)
            )
            self.session.add(ua)
        else:
            # Update existing record
            ua.last_tested = datetime.now(timezone.utc)
            if is_working:
                ua.status = 'working'
                ua.fail_count = 0
            else:
                ua.fail_count += 1
                if ua.fail_count >= 3:
                    ua.status = 'retired'
                else:
                    ua.status = 'failing'
        
        self.session.commit()
    
    def scrape_new_user_agents(self) -> List[str]:
        """Scrape new user agents from useragents.me"""
        try:
            from utils.http_utils import make_request
            import json
            
            html = make_request("https://www.useragents.me/")
            
            soup = BeautifulSoup(html, "html.parser")
            ta = soup.select_one('#most-common-desktop-useragents-json-csv textarea')
            
            if not ta:
                return []
            
            content = ta.get_text().strip()
            
            # Try to parse as JSON first (new format)
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    user_agents = []
                    for item in data:
                        if isinstance(item, dict) and 'ua' in item:
                            user_agents.append(item['ua'])
                        elif isinstance(item, str):
                            user_agents.append(item)
                    return user_agents[:50]  # Limit to first 50
            except json.JSONDecodeError:
                # Fall back to old format (plain text with quotes)
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                user_agents = []
                for line in lines:
                    if line.startswith('"') and line.endswith('"'):
                        user_agents.append(line[1:-1])  # Remove quotes
                return user_agents[:50]  # Limit to first 50
            
            return []
            
        except Exception as e:
            logger.error(f"Error scraping user agents: {e}")
            return []
    
    def import_user_agents(self, user_agents: List[str]):
        """Import new user agents into the database"""
        for ua_str in user_agents:
            # Check if already exists
            existing = self.session.query(UserAgent).filter(UserAgent.user_agent == ua_str).first()
            if not existing:
                ua = UserAgent(
                    user_agent=ua_str,
                    status='unknown'
                )
                self.session.add(ua)
        
        self.session.commit()
    
    def refresh_user_agents(self):
        """Refresh user agent pool by scraping and testing"""
        # Scrape new user agents
        new_uas = self.scrape_new_user_agents()
        if new_uas:
            self.import_user_agents(new_uas)
        
        # Test existing unknown user agents
        unknown_uas = self.session.query(UserAgent).filter(
            UserAgent.status == 'unknown'
        ).limit(20).all()
        
        for ua in unknown_uas:
            is_working = self.test_user_agent(ua.user_agent)
            self.update_user_agent_status(ua.user_agent, is_working)
    
    def cleanup_old_user_agents(self, days_old: int = 30):
        """Remove user agents that haven't been tested recently"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        old_uas = self.session.query(UserAgent).filter(
            and_(
                UserAgent.last_tested < cutoff_date,
                UserAgent.status.in_(['failing', 'retired'])
            )
        ).all()
        
        for ua in old_uas:
            self.session.delete(ua)
        
        self.session.commit()
        return len(old_uas)
        
