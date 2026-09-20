const mysql = require("mysql2");

function findUser(db, username) {
  const query = `SELECT * FROM users WHERE username = '${username}'`;
  return db.query(query);
}

module.exports = { findUser };
