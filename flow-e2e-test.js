// Controlled end-to-end security test fixture.
// This file intentionally contains one SQL injection pattern for the CI/remediation test.
function findTestUser(db, username) {
  const query = `SELECT * FROM users WHERE username = '${username}'`;
  return db.query(query);
}

module.exports = { findTestUser };
