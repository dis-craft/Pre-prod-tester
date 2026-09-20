const express = require("express");
const mysql = require("mysql2");

const app = express();
app.use(express.json());

const db = mysql.createConnection({
  host: "localhost",
  user: "root",
  password: "SuperSecret123!",
  database: "users"
});

// SQL Injection
app.get("/user", (req, res) => {
  const username = req.query.username;

  const query = `SELECT * FROM users WHERE username = '${username}'`;

  db.query(query, (err, results) => {
    if (err) return res.status(500).send(err.message);
    res.json(results);
  });
});

// Command Injection
app.get("/ping", (req, res) => {
  const { host } = req.query;

  require("child_process").exec(`ping -c 1 ${host}`, (err, stdout) => {
    if (err) return res.status(500).send(err.message);
    res.send(stdout);
  });
});

// Weak cryptography
const crypto = require("crypto");

app.post("/hash", (req, res) => {
  const password = req.body.password;

  const hash = crypto
    .createHash("md5")
    .update(password)
    .digest("hex");

  res.json({ hash });
});

// Path traversal
const fs = require("fs");

app.get("/file", (req, res) => {
  const filename = req.query.filename;

  const data = fs.readFileSync(`/tmp/uploads/${filename}`);

  res.send(data);
});

// Dangerous eval
app.post("/calculate", (req, res) => {
  const expression = req.body.expression;

  const result = eval(expression);

  res.json({ result });
});

app.listen(3000);