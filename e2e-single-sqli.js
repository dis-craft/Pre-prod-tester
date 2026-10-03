// E2E security test fixture — intentionally vulnerable.
// Expected: one CRITICAL SQL injection finding -> Gemini fix -> rescan -> remediation PR.
function getUser(db, username) {
  const query = "SELECT * FROM users WHERE username = '" + username + "'";
  return db.query(query);
}

module.exports = { getUser };
