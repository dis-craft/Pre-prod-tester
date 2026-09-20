/**
 * Pipeline Test Suite: 9 Intentional Security Vulnerabilities
 * Designed for testing SAST, pre-prod security scanners, and AI remediation pipelines.
 * All modules use standard Node.js built-ins so the code is fully executable without extra dependencies.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { exec } = require('child_process');
const url = require('url');

// =============================================================================
// Vulnerability 1: Hardcoded Sensitive Credentials (CWE-798)
// Issue: Secret tokens and keys should never be committed into source code.
// =============================================================================
const API_SECRET_KEY = "sk_live_prod_998877665544332211aabbccddeeff";
const JWT_SIGNING_SECRET = "super_secret_signing_key_do_not_share_123!";

function getAuthHeader() {
  return `Bearer ${API_SECRET_KEY}`;
}

// =============================================================================
// Vulnerability 2: SQL Injection (CWE-89)
// Issue: Untrusted user input is directly concatenated into a raw database query.
// =============================================================================
function queryUserAccount(mockDb, username) {
  const query = "SELECT * FROM accounts WHERE username = '" + username + "' AND active = 1";
  if (mockDb && typeof mockDb.query === 'function') {
    return mockDb.query(query);
  }
  return { executedQuery: query };
}

// =============================================================================
// Vulnerability 3: OS Command Injection (CWE-78)
// Issue: User input concatenated into shell command string executed via child_process.exec.
// =============================================================================
function pingHost(host, callback) {
  const command = `ping -c 1 ${host}`;
  return exec(command, (err, stdout, stderr) => {
    if (callback) callback(err, stdout, stderr);
  });
}

// =============================================================================
// Vulnerability 4: Path Traversal / Arbitrary File Read (CWE-22)
// Issue: Unsanitized filename allows directory traversal sequences (e.g. '../../etc/passwd').
// =============================================================================
function readReportFile(fileName) {
  const reportsDir = path.join(__dirname, 'data');
  const targetPath = path.join(reportsDir, fileName);
  if (fs.existsSync(targetPath)) {
    return fs.readFileSync(targetPath, 'utf8');
  }
  return null;
}

// =============================================================================
// Vulnerability 5: Broken / Weak Cryptographic Hash (CWE-327 / CWE-916)
// Issue: MD5 is cryptographically broken and should not be used for hashing passwords.
// =============================================================================
function hashUserPassword(plainPassword) {
  return crypto.createHash('md5').update(plainPassword).digest('hex');
}

// =============================================================================
// Vulnerability 6: Insecure Code Execution / Code Injection (CWE-95)
// Issue: Executing arbitrary strings via eval() can allow remote code execution.
// =============================================================================
function computeUserExpression(mathExpression) {
  // Evaluates user-supplied dynamic expression directly
  const result = eval(mathExpression);
  return result;
}

// =============================================================================
// Vulnerability 7: Server-Side Request Forgery (SSRF) (CWE-918)
// Issue: Fetching arbitrary user-supplied URLs allows internal network scanning/access.
// =============================================================================
function fetchRemoteWebhook(targetUrl, callback) {
  return http.get(targetUrl, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      if (callback) callback(null, data);
    });
  }).on('error', (err) => {
    if (callback) callback(err);
  });
}

// =============================================================================
// Vulnerability 8: Reflected Cross-Site Scripting (XSS) (CWE-79)
// Issue: Reflecting unescaped user parameter directly into an HTML response.
// =============================================================================
function renderUserProfile(username) {
  // Renders unescaped user parameter directly in HTML
  const htmlResponse = `
    <!DOCTYPE html>
    <html>
      <head><title>User Profile</title></head>
      <body>
        <h1>Welcome, ${username}!</h1>
      </body>
    </html>
  `;
  return htmlResponse;
}

// =============================================================================
// Vulnerability 9: Unvalidated Open Redirect (CWE-601)
// Issue: Redirecting users to an arbitrary external URL without origin validation.
// =============================================================================
function handleUserRedirect(res, returnUrl) {
  // Directly sends a 302 redirect header to the user-controlled destination
  res.writeHead(302, {
    Location: returnUrl
  });
  res.end();
}

// =============================================================================
// Working HTTP Server Dispatcher (Executable Node.js Service)
// =============================================================================
const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const pathname = parsedUrl.pathname;
  const query = parsedUrl.query;

  try {
    if (pathname === '/auth-info') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ auth: getAuthHeader() }));
    } else if (pathname === '/search') {
      const result = queryUserAccount(null, query.username || '');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    } else if (pathname === '/ping') {
      pingHost(query.host || '127.0.0.1', (err, stdout) => {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end(stdout || (err && err.message) || 'Ping finished');
      });
    } else if (pathname === '/read-file') {
      const content = readReportFile(query.filename || 'default.txt');
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end(content || 'File not found');
    } else if (pathname === '/hash') {
      const hashed = hashUserPassword(query.password || '');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ hash: hashed }));
    } else if (pathname === '/calculate') {
      const output = computeUserExpression(query.expr || '2 + 2');
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ result: output }));
    } else if (pathname === '/fetch-url') {
      fetchRemoteWebhook(query.url || 'http://example.com', (err, data) => {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end(err ? err.message : data);
      });
    } else if (pathname === '/profile') {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(renderUserProfile(query.username || 'Guest'));
    } else if (pathname === '/redirect') {
      handleUserRedirect(res, query.returnUrl || '/');
    } else {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end('Pipeline Security Test Service is running.');
    }
  } catch (err) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end('Error: ' + err.message);
  }
});

module.exports = {
  API_SECRET_KEY,
  JWT_SIGNING_SECRET,
  getAuthHeader,
  queryUserAccount,
  pingHost,
  readReportFile,
  hashUserPassword,
  computeUserExpression,
  fetchRemoteWebhook,
  renderUserProfile,
  handleUserRedirect,
  server
};

if (require.main === module) {
  const PORT = process.env.PORT || 4000;
  server.listen(PORT, () => {
    console.log(`Pipeline test server listening on port ${PORT}`);
  });
}

