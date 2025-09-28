# Real Estate Project Test Suite

This directory contains comprehensive tests for the real estate data scraping and processing pipeline.

## Test Structure

### Core Test Files

- **`test_comprehensive_error_handling.py`** - Comprehensive error handling and edge case tests
- **`test_job_runner_comprehensive.py`** - Job runner functionality and retry logic
- **`test_zestimate_helper_comprehensive.py`** - Zillow zestimate fetching and parsing
- **`test_specfic_home_info_helper_comprehensive.py`** - Redfin property data extraction
- **`test_homes_from_zipcode_helper_comprehensive.py`** - Zipcode-based home fetching
- **`test_user_agent_service_comprehensive.py`** - User agent management and testing
- **`test_http_utils_comprehensive.py`** - HTTP request utilities and error handling

### Legacy Test Files

- **`test_*.py`** - Original test files (moved from root directory)
- **`test_integration.py`** - Integration tests
- **`test_*_helper.py`** - Individual helper function tests

### Test Data

- **`redfin_individual_homes_htmls/`** - Sample Redfin HTML files for testing
- **`redfin_zipcode_htmls/`** - Sample Redfin zipcode HTML files for testing

### Configuration

- **`conftest.py`** - Pytest configuration and shared fixtures
- **`__init__.py`** - Package initialization
- **`run_tests.py`** - Test runner script

## Running Tests

### Quick Start

```bash
# Run all tests
python tests/run_tests.py

# Run with verbose output
python tests/run_tests.py --verbose

# Run with coverage
python tests/run_tests.py --coverage

# Interactive test selection
python tests/run_tests.py --interactive
```

### Using pytest directly

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_job_runner_comprehensive.py -v

# Run specific test class
pytest tests/test_comprehensive_error_handling.py::TestErrorHandling -v

# Run specific test method
pytest tests/test_zestimate_helper_comprehensive.py::TestGetZestimate::test_get_zestimate_success_http -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Test Categories

1. **All tests** - Complete test suite
2. **Error handling tests** - Comprehensive error scenarios
3. **Job runner tests** - Pipeline job processing
4. **Zestimate helper tests** - Zillow data fetching
5. **Home info helper tests** - Redfin data extraction
6. **Homes from zipcode tests** - Zipcode-based fetching
7. **User agent service tests** - User agent management
8. **HTTP utils tests** - HTTP request utilities
9. **Integration tests** - End-to-end workflows
10. **Legacy tests** - Original test files

## Test Coverage

### Error Handling Tests

- **Input validation** - None, empty, invalid inputs
- **Network errors** - Connection failures, timeouts, HTTP errors
- **Database errors** - Connection loss, constraint violations
- **Parsing errors** - Malformed JSON, missing data
- **Edge cases** - Very large data, unicode characters, special cases

### Functional Tests

- **Happy path scenarios** - Normal operation flows
- **Data transformation** - Input/output validation
- **Database operations** - CRUD operations, transactions
- **API interactions** - HTTP requests, response handling

### Integration Tests

- **End-to-end workflows** - Complete pipeline execution
- **Component interaction** - Module integration
- **Data flow validation** - Data consistency across components

## Test Fixtures

### Common Fixtures (conftest.py)

- **`mock_session`** - Mock database session
- **`sample_property_payload`** - Sample property data
- **`sample_redfin_html`** - Sample Redfin HTML
- **`sample_zillow_html`** - Sample Zillow HTML
- **`sample_job_payload`** - Sample job data
- **`mock_http_response`** - Mock HTTP response
- **`mock_playwright`** - Mock Playwright browser

### Custom Fixtures

Each test file may define additional fixtures specific to its testing needs.

## Test Data

### Sample HTML Files

The `redfin_individual_homes_htmls/` and `redfin_zipcode_htmls/` directories contain real HTML samples from Redfin for testing parsing logic.

### Mock Data

Tests use mock data to avoid external dependencies and ensure consistent, predictable results.

## Best Practices

### Writing Tests

1. **Use descriptive test names** - Clear indication of what is being tested
2. **Test one thing at a time** - Each test should have a single responsibility
3. **Use fixtures** - Reuse common test data and setup
4. **Mock external dependencies** - Avoid network calls and database operations
5. **Test edge cases** - Include boundary conditions and error scenarios
6. **Assert specific outcomes** - Verify exact expected results

### Test Organization

1. **Group related tests** - Use test classes for logical grouping
2. **Use consistent naming** - Follow naming conventions
3. **Keep tests independent** - Tests should not depend on each other
4. **Clean up after tests** - Use fixtures for setup and teardown

### Error Testing

1. **Test all error paths** - Ensure error handling works correctly
2. **Verify error messages** - Check that appropriate errors are raised
3. **Test recovery mechanisms** - Verify retry logic and fallbacks
4. **Test edge cases** - Include boundary conditions and unusual inputs

## Debugging Tests

### Common Issues

1. **Import errors** - Check that all modules are properly imported
2. **Fixture not found** - Ensure fixtures are defined in conftest.py or test file
3. **Mock not working** - Verify mock setup and call assertions
4. **Database connection** - Use mock sessions for database tests

### Debugging Commands

```bash
# Run single test with debug output
pytest tests/test_specific.py::test_method -v -s

# Run with pdb debugger
pytest tests/test_specific.py --pdb

# Show local variables on failure
pytest tests/test_specific.py --tb=long

# Run with warnings
pytest tests/test_specific.py --disable-warnings
```

## Continuous Integration

### GitHub Actions

Tests should be run automatically on:
- Pull requests
- Main branch pushes
- Scheduled runs

### Test Requirements

Ensure all tests pass before:
- Merging pull requests
- Deploying to production
- Releasing new versions

## Contributing

### Adding New Tests

1. **Follow naming conventions** - Use descriptive names
2. **Add to appropriate category** - Group with related tests
3. **Include error cases** - Test both success and failure scenarios
4. **Update documentation** - Document new test functionality

### Test Maintenance

1. **Keep tests updated** - Update tests when code changes
2. **Remove obsolete tests** - Clean up tests for removed functionality
3. **Optimize test performance** - Use efficient mocking and fixtures
4. **Review test coverage** - Ensure adequate coverage of critical paths

## Performance Considerations

### Test Speed

- **Use mocks** - Avoid real network calls and database operations
- **Minimize setup** - Keep test setup lightweight
- **Run in parallel** - Use pytest-xdist for parallel execution
- **Selective testing** - Run only relevant tests during development

### Resource Usage

- **Clean up resources** - Properly close connections and files
- **Limit test data** - Use minimal test datasets
- **Avoid heavy operations** - Mock computationally expensive operations

## Troubleshooting

### Common Problems

1. **Tests failing intermittently** - Check for race conditions or timing issues
2. **Mock not called** - Verify mock setup and method signatures
3. **Database errors** - Ensure proper session management in tests
4. **Import errors** - Check Python path and module imports

### Getting Help

1. **Check test logs** - Review test output for error details
2. **Run individual tests** - Isolate problematic tests
3. **Use debugger** - Step through failing tests
4. **Review recent changes** - Check if recent code changes broke tests
