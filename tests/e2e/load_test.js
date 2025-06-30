import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '5m', target: 10 },   // Stay at 10 users
    { duration: '2m', target: 20 },   // Ramp up to 20 users
    { duration: '5m', target: 20 },   // Stay at 20 users
    { duration: '2m', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests must complete below 2s
    http_req_failed: ['rate<0.1'],     // Error rate must be below 10%
    errors: ['rate<0.1'],              // Custom error rate below 10%
  },
};

// Test data
const TEST_SKUS = ['SKU-ABC', 'SKU-XYZ', 'SKU-ABC-V2', 'Product-X', 'Product-Y'];
const API_BASE_URL = __ENV.API_BASE_URL || 'http://localhost:8080/api';

// Test scenarios
export default function () {
  const sku = TEST_SKUS[Math.floor(Math.random() * TEST_SKUS.length)];
  
  // Test forecast API
  testForecastAPI(sku);
  
  // Test RAG API
  testRAGAPI(sku);
  
  // Test health endpoints
  testHealthEndpoints();
  
  sleep(1);
}

function testForecastAPI(sku) {
  const horizon = Math.floor(Math.random() * 90) + 7; // 7-90 days
  
  const response = http.get(`${API_BASE_URL}/forecast/${sku}?horizon=${horizon}`, {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '30s',
  });
  
  const success = check(response, {
    'forecast API status is 200': (r) => r.status === 200,
    'forecast API response time < 5s': (r) => r.timings.duration < 5000,
    'forecast API has valid response': (r) => {
      try {
        const data = JSON.parse(r.body);
        return data.sku === sku && Array.isArray(data.forecast);
      } catch (e) {
        return false;
      }
    },
  });
  
  if (!success) {
    errorRate.add(1);
    console.error(`Forecast API failed for ${sku}: ${response.status} - ${response.body}`);
  } else {
    errorRate.add(0);
  }
}

function testRAGAPI(sku) {
  const queries = [
    `What is the forecast for ${sku}?`,
    `Why is ${sku} trending up?`,
    `Compare ${sku} with other products`,
    `Show me marketing campaigns for ${sku}`,
  ];
  
  const query = queries[Math.floor(Math.random() * queries.length)];
  
  const payload = JSON.stringify({
    query: query,
    sku: sku,
    top_k: 3,
  });
  
  const response = http.post(`${API_BASE_URL}/ask`, payload, {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: '30s',
  });
  
  const success = check(response, {
    'RAG API status is 200': (r) => r.status === 200,
    'RAG API response time < 10s': (r) => r.timings.duration < 10000,
    'RAG API has valid response': (r) => {
      try {
        const data = JSON.parse(r.body);
        return data.query === query && typeof data.answer === 'string';
      } catch (e) {
        return false;
      }
    },
  });
  
  if (!success) {
    errorRate.add(1);
    console.error(`RAG API failed for query "${query}": ${response.status} - ${response.body}`);
  } else {
    errorRate.add(0);
  }
}

function testHealthEndpoints() {
  const healthResponse = http.get(`${API_BASE_URL}/health`, {
    timeout: '5s',
  });
  
  const success = check(healthResponse, {
    'health endpoint status is 200': (r) => r.status === 200,
    'health endpoint response time < 1s': (r) => r.timings.duration < 1000,
  });
  
  if (!success) {
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

// Setup function
export function setup() {
  console.log('Starting load test...');
  console.log(`API Base URL: ${API_BASE_URL}`);
  console.log(`Test SKUs: ${TEST_SKUS.join(', ')}`);
  
  // Verify API is accessible
  const healthCheck = http.get(`${API_BASE_URL}/health`);
  if (healthCheck.status !== 200) {
    throw new Error(`API health check failed: ${healthCheck.status}`);
  }
  
  console.log('API health check passed, starting load test...');
}

// Teardown function
export function teardown(data) {
  console.log('Load test completed');
}

// Handle summary
export function handleSummary(data) {
  return {
    'load-test-results.json': JSON.stringify(data, null, 2),
    stdout: `
Load Test Summary:
==================
Total Requests: ${data.metrics.http_reqs.count}
Failed Requests: ${data.metrics.http_req_failed.count} (${(data.metrics.http_req_failed.rate * 100).toFixed(2)}%)
Average Response Time: ${data.metrics.http_req_duration.avg.toFixed(2)}ms
95th Percentile: ${data.metrics['http_req_duration{p(95)}'].toFixed(2)}ms
Max Response Time: ${data.metrics.http_req_duration.max.toFixed(2)}ms

Thresholds:
- 95th percentile < 2000ms: ${data.metrics['http_req_duration{p(95)}'] < 2000 ? 'PASS' : 'FAIL'}
- Error rate < 10%: ${data.metrics.http_req_failed.rate < 0.1 ? 'PASS' : 'FAIL'}
- Custom error rate < 10%: ${data.metrics.errors.rate < 0.1 ? 'PASS' : 'FAIL'}
==================
`,
  };
}