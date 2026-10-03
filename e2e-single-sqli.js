// E2E security test fixture — intentionally vulnerable.
// Expected: one CRITICAL SQL injection finding -> Gemini fix -> rescan -> remediation PR.
function getUser(db, username) {
  return db.query("SELECT * FROM users WHERE username = ?", [username]);
}

module.exports = { getUser };
