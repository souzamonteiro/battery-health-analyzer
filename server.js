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

//const HTTP_PORT = Number(process.env.PORT || 8000);
//const HTTPS_PORT = Number(process.env.SSL_PORT || 8443);
const HTTP_PORT = Number(process.env.PORT || 9095);
const HTTPS_PORT = Number(process.env.SSL_PORT || 9543);
const ENABLE_SSL = process.env.ENABLE_SSL !== 'false';
const HTTPS_ONLY = process.env.HTTPS_ONLY === 'true';
const SSL_KEY = process.env.SSL_KEY || path.join(ROOT, 'localhost-key.pem');
const SSL_CERT = process.env.SSL_CERT || path.join(ROOT, 'localhost.pem');
const DATASET_SALT = process.env.DATASET_SALT || process.env.OMBTD_DATASET_SALT || 'change-this-dataset-salt';

const METADATA_PUBLIC_SUFFIX = '.device.json';
const METADATA_PRIVATE_SUFFIX = '.device.private.json';

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

function asNonEmptyString(value, fallback = 'unknown') {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : fallback;
}

function parseTelemetryDeviceId(value) {
  if (typeof value !== 'string') return null;
  const candidate = value.trim();
  if (!candidate) return null;
  if (!/^[a-zA-Z0-9-]{8,128}$/.test(candidate)) return null;
  return candidate;
}

function buildPublicDeviceId(telemetryDeviceId) {
  if (!telemetryDeviceId) return null;
  const hash = crypto
    .createHash('sha256')
    .update(`${telemetryDeviceId}:${DATASET_SALT}`, 'utf8')
    .digest('hex');
  return `dev_${hash.slice(0, 12)}`;
}

function isPublicMetadataFile(name) {
  return name.endsWith(METADATA_PUBLIC_SUFFIX);
}

function isPrivateMetadataFile(name) {
  return name.endsWith(METADATA_PRIVATE_SUFFIX);
}

function isReportJsonFile(name) {
  return name.endsWith('.json') && !isPublicMetadataFile(name) && !isPrivateMetadataFile(name);
}

function parseDeviceMetadata(rawMetadata, req) {
  let parsed = {};
  if (typeof rawMetadata === 'string' && rawMetadata.trim().length > 0) {
    try {
      parsed = JSON.parse(rawMetadata);
    } catch (_error) {
      parsed = { raw: rawMetadata };
    }
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    parsed = {};
  }

  const transport = req.secure ? 'https' : 'http';
  const telemetryDeviceId = parseTelemetryDeviceId(parsed.telemetryDeviceId || parsed.deviceId || parsed.clientId);
  const publicDeviceId = buildPublicDeviceId(telemetryDeviceId);

  return {
    source: asNonEmptyString(parsed.source),
    platform: asNonEmptyString(parsed.platform),
    osName: asNonEmptyString(parsed.osName),
    osVersion: asNonEmptyString(parsed.osVersion),
    manufacturer: asNonEmptyString(parsed.manufacturer || parsed.brand),
    model: asNonEmptyString(parsed.model || parsed.device),
    brand: asNonEmptyString(parsed.brand),
    device: asNonEmptyString(parsed.device),
    product: asNonEmptyString(parsed.product),
    hardware: asNonEmptyString(parsed.hardware),
    fingerprint: asNonEmptyString(parsed.fingerprint),
    telemetryDeviceId,
    publicDeviceId,
    userAgent: req.get('user-agent') || 'unknown',
    requestIp: req.ip || req.socket?.remoteAddress || 'unknown',
    requestHost: req.get('host') || 'unknown',
    requestProtocol: transport,
    capturedAt: parsed.capturedAt || Date.now(),
    receivedAt: now(),
    extras: parsed,
  };
}

function toPublicDeviceMetadata(deviceMetadata) {
  return {
    source: deviceMetadata.source,
    platform: deviceMetadata.platform,
    osName: deviceMetadata.osName,
    osVersion: deviceMetadata.osVersion,
    manufacturer: deviceMetadata.manufacturer,
    model: deviceMetadata.model,
    brand: deviceMetadata.brand,
    device: deviceMetadata.device,
    product: deviceMetadata.product,
    hardware: deviceMetadata.hardware,
    capturedAt: deviceMetadata.capturedAt,
    receivedAt: deviceMetadata.receivedAt,
    publicDeviceId: deviceMetadata.publicDeviceId || null,
  };
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
  const mode = HTTPS_ONLY ? 'https-only' : (ENABLE_SSL ? 'http+https' : 'http-only');
  res.json({
    status: 'ok',
    service: 'battery-health-analyzer-api',
    mode,
    sslEnabled: ENABLE_SSL,
    httpsOnly: HTTPS_ONLY,
    httpPort: HTTP_PORT,
    httpsPort: HTTPS_PORT,
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
  const normalizedUploadName = originalName.endsWith('.csv') ? originalName : `${originalName}.csv`;
  const archivedUploadPath = path.join(UPLOAD_DIR, `${jobId}_${normalizedUploadName}`);
  const inputPath = path.join(jobDir, normalizedUploadName);
  const publicMetadataPath = path.join(jobDir, `${normalizedUploadName}${METADATA_PUBLIC_SUFFIX}`);
  const privateMetadataPath = path.join(jobDir, `${normalizedUploadName}${METADATA_PRIVATE_SUFFIX}`);
  const deviceMetadata = parseDeviceMetadata(req.body.deviceMetadata, req);
  const publicDeviceMetadata = toPublicDeviceMetadata(deviceMetadata);

  try {
    await fsp.mkdir(plotsDir, { recursive: true });
    await fsp.copyFile(req.file.path, archivedUploadPath);
    await fsp.rename(req.file.path, inputPath);
    await fsp.writeFile(publicMetadataPath, JSON.stringify(publicDeviceMetadata, null, 2), 'utf-8');
    await fsp.writeFile(privateMetadataPath, JSON.stringify(deviceMetadata, null, 2), 'utf-8');

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

    const jsonFiles = (await fsp.readdir(jobDir)).filter(isReportJsonFile);
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
      metadataUrl: `/api/analysis/${jobId}/metadata`,
      uploadedFile: path.basename(inputPath),
      metadataFile: path.basename(publicMetadataPath),
      publicDeviceId: publicDeviceMetadata.publicDeviceId,
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

app.get('/api/analysis/:jobId/metadata', async (req, res) => {
  const { jobId } = req.params;
  const jobDir = path.join(ANALYSIS_DIR, jobId);

  try {
    const metadataFiles = (await fsp.readdir(jobDir)).filter(isPublicMetadataFile);
    if (metadataFiles.length === 0) {
      res.status(404).json({ error: 'Metadata not found.' });
      return;
    }

    const metadata = JSON.parse(await fsp.readFile(path.join(jobDir, metadataFiles[0]), 'utf-8'));
    res.json({ jobId, metadata });
  } catch (_error) {
    res.status(404).json({ error: 'Metadata not found.' });
  }
});

app.get('/api/analysis/:jobId/report', async (req, res) => {
  const { jobId } = req.params;
  const jobDir = path.join(ANALYSIS_DIR, jobId);

  try {
    const jsonFiles = (await fsp.readdir(jobDir)).filter(isReportJsonFile);
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

const EXPORT_DIR = path.join(RUNTIME_DIR, 'ombtd_export');
const OMBTD_EXPORTER_SCRIPT = path.join(ROOT, 'export_ombtd.py');

app.post('/api/export-ombtd', async (_req, res) => {
  try {
    await fsp.mkdir(EXPORT_DIR, { recursive: true });

    const salt = DATASET_SALT;
    await runPython(OMBTD_EXPORTER_SCRIPT, [
      '--analyses-dir', ANALYSIS_DIR,
      '--out-dir', EXPORT_DIR,
      '--salt', salt,
    ]);

    const files = await fsp.readdir(EXPORT_DIR);
    const csvFiles = files.filter((f) => f.endsWith('.csv') || f === 'OMBTD_VERSION');

    const manifest = csvFiles.map((f) => ({
      name: f,
      url: `/api/ombtd/${encodeURIComponent(f)}`,
    }));

    res.json({
      status: 'ok',
      exportDir: EXPORT_DIR,
      schemaVersion: '1.0',
      files: manifest,
    });
  } catch (error) {
    res.status(500).json({ error: String(error.message || error) });
  }
});

app.get('/api/ombtd/:fileName', async (req, res) => {
  const fileName = path.basename(req.params.fileName);
  const filePath = path.join(EXPORT_DIR, fileName);

  try {
    await fsp.access(filePath);
    res.download(filePath, fileName);
  } catch (_error) {
    res.status(404).json({ error: 'OMBTD file not found.' });
  }
});

app.use(express.static(WWW_DIR));

app.get('*', (_req, res) => {
  res.sendFile(path.join(WWW_DIR, 'index.html'));
});

async function start() {
  await ensureDirectories();

  if (HTTPS_ONLY && !ENABLE_SSL) {
    throw new Error('HTTPS_ONLY=true requires ENABLE_SSL=true.');
  }

  const shouldStartHttp = !HTTPS_ONLY && !(ENABLE_SSL && HTTP_PORT === HTTPS_PORT);
  if (shouldStartHttp) {
    app.listen(HTTP_PORT, () => {
      log('INFO', `HTTP server running at http://localhost:${HTTP_PORT}`);
      log('INFO', `Serving static files from ${WWW_DIR}`);
    });
  } else {
    if (HTTPS_ONLY) {
      log('INFO', 'HTTP listener disabled because HTTPS_ONLY=true.');
    } else {
      log('WARN', `HTTP listener disabled because PORT (${HTTP_PORT}) equals SSL_PORT (${HTTPS_PORT}) with SSL enabled.`);
    }
    log('INFO', `Serving static files from ${WWW_DIR}`);
  }

  if (ENABLE_SSL && fs.existsSync(SSL_KEY) && fs.existsSync(SSL_CERT)) {
    const credentials = {
      key: fs.readFileSync(SSL_KEY),
      cert: fs.readFileSync(SSL_CERT),
    };

    https.createServer(credentials, app).listen(HTTPS_PORT, () => {
      log('INFO', `HTTPS server running at https://localhost:${HTTPS_PORT}`);
    });
  } else if (ENABLE_SSL) {
    log('WARN', `HTTPS requested on port ${HTTPS_PORT}, but SSL_KEY or SSL_CERT is missing.`);
  }
}

start().catch((error) => {
  log('ERROR', String(error.message || error));
  process.exit(1);
});
