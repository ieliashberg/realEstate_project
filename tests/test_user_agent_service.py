#!/usr/bin/env python3
"""
Test script for UserAgentService functionality
"""

import sys
from src.database.connection import SessionLocal
from src.scrapers.user_agents.service import UserAgentService
from src.scrapers.user_agents.models import UserAgent

def test_user_agent_service():
    """Test UserAgentService functionality"""
    print("🤖 Testing UserAgentService...")
    
    session = SessionLocal()
    ua_service = UserAgentService(session)
    
    try:
        # Test 1: Get working user agents (should work even if empty)
        print("\n1. Testing get_working_user_agents...")
        working_uas = ua_service.get_working_user_agents(5)
        print(f"    Found {len(working_uas)} working user agents")
        if working_uas:
            print(f"    Sample UA: {working_uas[0][:50]}...")
        else:
            print("     No working user agents found (expected if database is empty)")
        
        # Test 2: Import some test user agents
        print("\n2. Testing import_user_agents...")
        test_user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        
        ua_service.import_user_agents(test_user_agents)
        print(f"    Imported {len(test_user_agents)} user agents")
        
        # Test 3: Get working user agents again (should have some now)
        print("\n3. Testing get_working_user_agents after import...")
        working_uas = ua_service.get_working_user_agents(5)
        print(f"    Found {len(working_uas)} working user agents")
        if working_uas:
            print(f"    Sample UA: {working_uas[0][:50]}...")
        
        # Test 4: Test a user agent (mock test)
        print("\n4. Testing test_user_agent...")
        if working_uas:
            test_ua = working_uas[0]
            is_working = ua_service.test_user_agent(test_ua)
            print(f"    User agent working: {is_working}")
        
        # Test 5: Update user agent status
        print("\n5. Testing update_user_agent_status...")
        if working_uas:
            test_ua = working_uas[0]
            ua_service.update_user_agent_status(test_ua, True)
            print(f"    Updated user agent status to working=True")
        
        # Test 6: Get user agent count
        print("\n6. Testing database query...")
        all_uas = session.query(UserAgent).all()
        print(f"    Total user agents in database: {len(all_uas)}")
        
        # Show some stats
        working_count = len([ua for ua in all_uas if ua.status == 'working'])
        failing_count = len([ua for ua in all_uas if ua.status == 'failing'])
        unknown_count = len([ua for ua in all_uas if ua.status == 'unknown'])
        
        print(f"    Status breakdown:")
        print(f"      - Working: {working_count}")
        print(f"      - Failing: {failing_count}")
        print(f"      - Unknown: {unknown_count}")
        
        return True
        
    except Exception as e:
        print(f" UserAgentService test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def test_user_agent_database_model():
    """Test UserAgent database model"""
    print("\n  Testing UserAgent database model...")
    
    session = SessionLocal()
    
    try:
        # Test creating a UserAgent record
        test_ua = UserAgent(
            user_agent="Test User Agent String",
            status='unknown',
            fail_count=0
        )
        
        session.add(test_ua)
        session.commit()
        print("    Created UserAgent record")
        
        # Test querying the record
        found_ua = session.query(UserAgent).filter_by(user_agent="Test User Agent String").first()
        if found_ua:
            print(f"    Retrieved UserAgent: {found_ua}")
            print(f"    ID: {found_ua.id}")
            print(f"    Status: {found_ua.status}")
            print(f"    Fail count: {found_ua.fail_count}")
        else:
            print("    Could not retrieve UserAgent record")
            return False
        
        # Clean up test record
        session.delete(found_ua)
        session.commit()
        print("   🧹 Cleaned up test record")
        
        return True
        
    except Exception as e:
        print(f" UserAgent model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def test_user_agent_integration():
    """Test user agent integration with HTTP requests"""
    print("\n🌐 Testing user agent integration...")
    
    try:
        from src.utils.http import fetch_html_via_https
        
        # Test HTTP request with user agent rotation
        url = 'https://httpbin.org/user-agent'
        result = fetch_html_via_https(url)
        
        if result and 'user-agent' in result.lower():
            print("    HTTP request with user agent rotation successful")
            print(f"    Response preview: {result[:100]}...")
            return True
        else:
            print("    HTTP request failed or no user agent detected")
            return False
            
    except Exception as e:
        print(f" User agent integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all UserAgentService tests"""
    print(" UserAgentService Test Suite")
    print("=" * 50)
    
    tests = [
        ("UserAgent Database Model", test_user_agent_database_model),
        ("UserAgentService Core", test_user_agent_service),
        ("User Agent Integration", test_user_agent_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f" {test_name} crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print(" Test Results Summary:")
    
    passed = 0
    for test_name, result in results:
        status = " PASS" if result else " FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print(" All UserAgentService tests passed!")
        return 0
    else:
        print("  Some UserAgentService tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
