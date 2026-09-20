const mysql = require("mysql2");

function findUser(db, username) {
  const query = `SELECT * FROM users WHERE username = '${username}'`; // E2E: trigger SQL injection remediation
  return db.query(query);
}

module.exports = { findUser };

// E2E remediation trigger: intentionally keep this fixture vulnerable for the test.
