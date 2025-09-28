#!/usr/bin/env python3
"""
Test script for Redfin and Zillow functionality
"""

import sys
from homes_from_zipcode_helper import fetch_homes_json_via_playwright
from zestimate_helper import get_zestimate

def test_redfin_zipcode_fetch():
    """Test Redfin zipcode fetching via playwright"""
    print(" Testing Redfin Zipcode Fetch...")
    
    test_zipcode = '94102'  # San Francisco
    url = f'https://www.redfin.com/zipcode/{test_zipcode}'
    
    try:
        result, request_url = fetch_homes_json_via_playwright(url)
        
        if result and len(str(result)) > 100:  # Should be a substantial JSON response
            print(f" Redfin fetch successful!")
            print(f"    Result length: {len(str(result))} characters")
            print(f"   🔗 Request URL: {request_url[:100]}...")
            
            # Try to extract some basic info
            if isinstance(result, dict):
                # Check if it's the direct payload structure
                if 'payload' in result and 'homes' in result['payload']:
                    homes_count = len(result['payload']['homes'])
                    print(f"     Found {homes_count} homes")
                    
                    # Show first home's basic info
                    if homes_count > 0:
                        first_home = result['payload']['homes'][0]
                        price = first_home.get('price', {}).get('value', 'N/A')
                        address = first_home.get('streetLine', {}).get('value', 'N/A')
                        print(f"   💰 Sample: {address} - ${price:,}")
                # Check if it's the direct homes array structure
                elif 'homes' in result:
                    homes_count = len(result['homes'])
                    print(f"     Found {homes_count} homes")
                    
                    # Show first home's basic info
                    if homes_count > 0:
                        first_home = result['homes'][0]
                        price = first_home.get('price', {}).get('value', 'N/A')
                        address = first_home.get('streetLine', {}).get('value', 'N/A')
                        print(f"   💰 Sample: {address} - ${price:,}")
                # Check if it's a list of homes directly
                elif isinstance(result, list) and len(result) > 0:
                    homes_count = len(result)
                    print(f"     Found {homes_count} homes")
                    
                    # Show first home's basic info
                    first_home = result[0]
                    if isinstance(first_home, dict):
                        price = first_home.get('price', {}).get('value', 'N/A')
                        address = first_home.get('streetLine', {}).get('value', 'N/A')
                        print(f"   💰 Sample: {address} - ${price:,}")
                else:
                    # Show some structure info for debugging
                    print(f"    Result structure: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            
            return True
        else:
            print(f" Redfin fetch failed or returned minimal data")
            print(f"   Result: {result}")
            return False
            
    except Exception as e:
        print(f" Redfin fetch error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_zillow_zestimate():
    """Test Zillow zestimate functionality"""
    print("\n Testing Zillow Zestimate...")
    
    test_cases = [
        ('123 Main St', 'San Francisco', 'CA', '94102'),
        ('555 Fulton St', 'San Francisco', 'CA', '94102'),
        ('1169 Sesame Dr', 'Sunnyvale', 'CA', '94087')
    ]
    
    success_count = 0
    
    for address, city, state, zipcode in test_cases:
        try:
            result = get_zestimate(address, city, state, zipcode)
            
            if result and isinstance(result, tuple) and len(result) >= 3:
                zestimate, zestimate_high, zestimate_low = result[:3]
                
                if zestimate and zestimate > 0:
                    print(f" {address}, {city}, {state} {zipcode}")
                    print(f"   💵 Zestimate: ${zestimate:,}")
                    if zestimate_high:
                        print(f"    High: ${zestimate_high:,}")
                    if zestimate_low:
                        print(f"    Low: ${zestimate_low:,}")
                    success_count += 1
                else:
                    print(f"  {address}: No zestimate data available")
            else:
                print(f" {address}: Invalid result format: {result}")
                
        except Exception as e:
            print(f" {address}: Error - {e}")
    
    print(f"\n Zillow test results: {success_count}/{len(test_cases)} successful")
    return success_count > 0

def test_http_fetch():
    """Test basic HTTP fetching functionality"""
    print("\n🌐 Testing HTTP Fetch...")
    
    try:
        from utils.http_utils import fetch_html_via_https
        
        # Test with a simple endpoint
        url = 'https://httpbin.org/user-agent'
        result = fetch_html_via_https(url)
        
        if result and 'user-agent' in result.lower():
            print(" HTTP fetch working with user agent rotation")
            return True
        else:
            print(" HTTP fetch failed or no user agent detected")
            return False
            
    except Exception as e:
        print(f" HTTP fetch error: {e}")
        return False

def main():
    """Run all tests"""
    print(" Real Estate Pipeline Test Suite")
    print("=" * 50)
    
    tests = [
        ("HTTP Fetch", test_http_fetch),
        ("Redfin Zipcode", test_redfin_zipcode_fetch),
        ("Zillow Zestimate", test_zillow_zestimate)
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
        print(" All tests passed! Your pipeline is working correctly.")
        return 0
    else:
        print("  Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
