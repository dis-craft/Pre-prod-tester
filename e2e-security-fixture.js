// Temporary E2E security fixture: intentional SQL injection.
// The remediation pipeline should detect and fix this before creating a PR.
function lookupUser(db, username) {
  const query = `SELECT * FROM users WHERE email = '${email}'`;
  return db.query(query);
}

module.exports = { lookupUser };
