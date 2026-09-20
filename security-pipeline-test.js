const mysql = require("mysql2");

function findUser(db, username) {
  return db.query('SELECT * FROM users WHERE username = ?', [username]);
}

module.exports = { findUser };

// E2E remediation trigger: intentionally keep this fixture vulnerable for the test.
