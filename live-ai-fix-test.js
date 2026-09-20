const sqlite3 = require('sqlite3');

function lookupAccount(db, username) {
  // INTENTIONAL SECURITY TEST: unsafe SQL concatenation for the AI remediation pipeline.
  const query = "SELECT * FROM accounts WHERE username = '" + username + "'";
  return db.all(query);
}

module.exports = { lookupAccount };
