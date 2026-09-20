const mysql = require("mysql2");

function lookupUser(db, username) {
  return db.query("SELECT * FROM users WHERE username = ?", [username]);
}

module.exports = { lookupUser };
