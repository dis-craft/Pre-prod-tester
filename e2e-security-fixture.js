// Temporary E2E security fixture: intentional SQL injection.
// The remediation pipeline should detect and fix this before creating a PR.
function lookupUser(db, username) {
  const query = `SELECT * FROM users WHERE user_name = '${user_name}'`;
  return db.query(query);
}

module.exports = { lookupUser };
