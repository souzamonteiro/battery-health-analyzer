#!/usr/bin/env node

const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const https = require('https');
const { spawn } = require('child_process');
const crypto = require('crypto');

const express = require('express');
const multer = require('multer');
const cors = require('cors');

const ROOT = __dirname;
const WWW_DIR = path.join(ROOT, 'www');
const RUNTIME_DIR = path.join(ROOT, 'runtime');
const UPLOAD_DIR = path.join(RUNTIME_DIR, 'uploads');
const ANALYSIS_DIR = path.join(RUNTIME_DIR, 'analyses');
const GENERATED_DIR = path.join(RUNTIME_DIR, 'generated');

const PYTHON_BIN = process.env.PYTHON_BIN || 'python3';
const ANALYZER_SCRIPT = path.join(ROOT, 'battery_bdf_analyzer_console.py');
const GENERATOR_SCRIPT = path.join(ROOT, 'generate_test_bdf_data.py');

const HTTP_PORT = Number(process.env.PORT || 8000);
const HTTPS_PORT = Number(process.env.SSL_PORT || 8443);
const ENABLE_SSL = process.env.ENABLE_SSL === 'true';
const SSL_KEY = process.env.SSL_KEY || path.join(ROOT, 'localhost-key.pem');
const SSL_CERT = process.env.SSL_CERT || path.join(ROOT, 'localhost.pem');

function now() {
  return new Date().toISOString();
}

function log(level, message) {
  console.log(`[${now()}] ${level}: ${message}`);
}

async function ensureDirectories() {
  await fsp.mkdir(WWW_DIR, { recursive: true });
  await fsp.mkdir(UPLOAD_DIR, { recursive: true });
  await fsp.mkdir(ANALYSIS_DIR, { recursive: true });
  await fsp.mkdir(GENERATED_DIR, { recursive: true });
}

function runPython(script, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(PYTHON_BIN, [script, ...args], {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    child.on('error', (error) => reject(error));

    child.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
        return;
      }

      reject(new Error(stderr.trim() || stdout.trim() || `${path.basename(script)} exited with code ${code}`));
    });
  });
}

function safeFilename(name) {
  return name.replace(/[^a-zA-Z0-9_.-]/g, '_');
}

function parseNumber(input, fallback) {
  const n = Number(input);
  return Number.isFinite(n) ? n : fallback;
}

const upload = multer({
  dest: UPLOAD_DIR,
  limits: {
    fileSize: 40 * 1024 * 1024,
  },
});

const app = express();
app.use(cors());
app.use(express.json({ limit: '1mb' }));

app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'battery-health-analyzer-api',
    timestamp: now(),
  });
});

app.post('/api/analyze', upload.single('batteryFile'), async (req, res) => {
  if (!req.file) {
    res.status(400).json({ error: 'No file uploaded. Send multipart/form-data with field "batteryFile".' });
    return;
  }

  const jobId = `an_${crypto.randomUUID()}`;
  const jobDir = path.join(ANALYSIS_DIR, jobId);
  const plotsDir = path.join(jobDir, 'plots');

  const eol = parseNumber(req.body.eol, 70);
  const svrDays = parseNumber(req.body.svrDays, 30);
  const originalName = safeFilename(req.file.originalname || 'uploaded.bdf.csv');
  const inputPath = path.join(jobDir, originalName.endsWith('.csv') ? originalName : `${originalName}.csv`);

  try {
    await fsp.mkdir(plotsDir, { recursive: true });
    await fsp.rename(req.file.path, inputPath);

    await runPython(ANALYZER_SCRIPT, [
      inputPath,
      '--json',
      '--json-dir',
      jobDir,
      '--outdir',
      plotsDir,
      '--eol',
      String(eol),
      '--svr-days',
      String(svrDays),
    ]);

    const jsonFiles = (await fsp.readdir(jobDir)).filter((name) => name.endsWith('.json'));
    if (jsonFiles.length === 0) {
      throw new Error('Analyzer did not produce a JSON report.');
    }

    const reportPath = path.join(jobDir, jsonFiles[0]);
    const report = JSON.parse(await fsp.readFile(reportPath, 'utf-8'));

    const plots = Array.isArray(report.saved_plots)
      ? report.saved_plots.map((plotPath) => {
          const fileName = path.basename(String(plotPath));
          return {
            name: fileName,
            url: `/api/analysis/${jobId}/plots/${encodeURIComponent(fileName)}`,
          };
        })
      : [];

    res.json({
      jobId,
      report,
      plots,
      reportUrl: `/api/analysis/${jobId}/report`,
      uploadedFile: path.basename(inputPath),
    });
  } catch (error) {
    try {
      await fsp.unlink(req.file.path);
    } catch (_e) {
      // no-op
    }
    res.status(500).json({ error: String(error.message || error) });
  }
});

app.get('/api/analysis/:jobId/report', async (req, res) => {
  const { jobId } = req.params;
  const jobDir = path.join(ANALYSIS_DIR, jobId);

  try {
    const jsonFiles = (await fsp.readdir(jobDir)).filter((name) => name.endsWith('.json'));
    if (jsonFiles.length === 0) {
      res.status(404).json({ error: 'Report not found.' });
      return;
    }

    const report = JSON.parse(await fsp.readFile(path.join(jobDir, jsonFiles[0]), 'utf-8'));
    res.json({ jobId, report });
  } catch (_error) {
    res.status(404).json({ error: 'Report not found.' });
  }
});

app.get('/api/analysis/:jobId/plots/:plotName', async (req, res) => {
  const { jobId, plotName } = req.params;
  const fileName = path.basename(plotName);
  const filePath = path.join(ANALYSIS_DIR, jobId, 'plots', fileName);

  try {
    await fsp.access(filePath);
    res.sendFile(filePath);
  } catch (_error) {
    res.status(404).json({ error: 'Plot not found.' });
  }
});

app.post('/api/generate-dataset', async (req, res) => {
  const payload = req.body || {};
  const generationId = `gen_${crypto.randomUUID()}`;
  const outputName = `${generationId}.bdf.csv`;
  const outputPath = path.join(GENERATED_DIR, outputName);

  const samples = parseNumber(payload.samples, 3000);
  const stepSeconds = parseNumber(payload.stepSeconds, 60);
  const startSoh = parseNumber(payload.startSoh, 99);
  const endSoh = parseNumber(payload.endSoh, 82);
  const seed = parseNumber(payload.seed, 42);

  try {
    await runPython(GENERATOR_SCRIPT, [
      '--output',
      outputPath,
      '--samples',
      String(samples),
      '--step-seconds',
      String(stepSeconds),
      '--start-soh',
      String(startSoh),
      '--end-soh',
      String(endSoh),
      '--seed',
      String(seed),
    ]);

    res.json({
      generationId,
      datasetPath: outputPath,
      datasetUrl: `/api/datasets/${encodeURIComponent(outputName)}`,
      parameters: { samples, stepSeconds, startSoh, endSoh, seed },
    });
  } catch (error) {
    res.status(500).json({ error: String(error.message || error) });
  }
});

app.get('/api/datasets/:fileName', async (req, res) => {
  const fileName = path.basename(req.params.fileName);
  const filePath = path.join(GENERATED_DIR, fileName);

  try {
    await fsp.access(filePath);
    res.download(filePath, fileName);
  } catch (_error) {
    res.status(404).json({ error: 'Dataset not found.' });
  }
});

app.use(express.static(WWW_DIR));

app.get('*', (_req, res) => {
  res.sendFile(path.join(WWW_DIR, 'index.html'));
});

async function start() {
  await ensureDirectories();

  app.listen(HTTP_PORT, () => {
    log('INFO', `HTTP server running at http://localhost:${HTTP_PORT}`);
    log('INFO', `Serving static files from ${WWW_DIR}`);
  });

  if (ENABLE_SSL && fs.existsSync(SSL_KEY) && fs.existsSync(SSL_CERT)) {
    const credentials = {
      key: fs.readFileSync(SSL_KEY),
      cert: fs.readFileSync(SSL_CERT),
    };

    https.createServer(credentials, app).listen(HTTPS_PORT, () => {
      log('INFO', `HTTPS server running at https://localhost:${HTTPS_PORT}`);
    });
  }
}

start().catch((error) => {
  log('ERROR', String(error.message || error));
  process.exit(1);
});
