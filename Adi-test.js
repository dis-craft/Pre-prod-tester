const sqlite3 = require('sqlite3');
const { exec } = require('child_process');
const fs = require('fs');

function lookupAccount(db, username) {
  // INTENTIONAL SECURITY TEST: unsafe SQL concatenation for the AI remediation pipeline.
  const query = "SELECT * FROM accounts WHERE username = '" + username + "'";
  return db.all(query);
}

function runBackup(targetDir, callback) {
  // INTENTIONAL SECURITY TEST: unsafe command execution / command injection.
  const cmd = `tar -czf backup.tar.gz ${targetDir}`;
  exec(cmd, callback);
}

function readUserReport(fileName) {
  // INTENTIONAL SECURITY TEST: unsanitized path concatenation / path traversal.
  const filePath = '/var/data/reports/' + fileName;
  return fs.readFileSync(filePath, 'utf8');
}

module.exports = { lookupAccount, runBackup, readUserReport };

