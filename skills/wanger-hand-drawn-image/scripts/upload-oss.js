#!/usr/bin/env node

const crypto = require("crypto");
const fs = require("fs");
const https = require("https");
const path = require("path");

const IMAGE_TYPES = new Map([
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".gif", "image/gif"],
  [".webp", "image/webp"],
  [".svg", "image/svg+xml"],
  [".avif", "image/avif"],
]);

function printHelp() {
  console.log(`Usage:
  node upload-oss.js --image <path> [options]

Options:
  --image <path>       Local generated image path. Required.
  --env <path>         Env file path. Default: <cwd>/.env
  --prefix <prefix>    OSS object key prefix. Default: articles
  --name <slug>        Base filename slug. Default: image
  --json               Print JSON output.
  --dry-run            Validate and print planned URL without uploading.
  --help               Show this help.`);
}

function parseArgs(argv) {
  const options = {
    image: "",
    envFile: path.join(process.cwd(), ".env"),
    prefix: "articles",
    name: "image",
    json: false,
    dryRun: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--image") {
      options.image = path.resolve(requireValue(argv, i));
      i += 1;
    } else if (arg.startsWith("--image=")) {
      options.image = path.resolve(arg.slice("--image=".length));
    } else if (arg === "--env") {
      options.envFile = path.resolve(requireValue(argv, i));
      i += 1;
    } else if (arg.startsWith("--env=")) {
      options.envFile = path.resolve(arg.slice("--env=".length));
    } else if (arg === "--prefix") {
      options.prefix = requireValue(argv, i);
      i += 1;
    } else if (arg.startsWith("--prefix=")) {
      options.prefix = arg.slice("--prefix=".length);
    } else if (arg === "--name") {
      options.name = requireValue(argv, i);
      i += 1;
    } else if (arg.startsWith("--name=")) {
      options.name = arg.slice("--name=".length);
    } else if (arg === "--json") {
      options.json = true;
    } else if (arg === "--dry-run") {
      options.dryRun = true;
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  return options;
}

function requireValue(argv, index) {
  const value = argv[index + 1];
  if (!value || value.startsWith("-")) {
    throw new Error(`Missing value for ${argv[index]}`);
  }
  return value;
}

function loadEnv(envFile) {
  if (!fs.existsSync(envFile)) {
    throw new Error(`Env file not found: ${envFile}`);
  }

  const env = {};
  const content = fs.readFileSync(envFile, "utf8");
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const equalsIndex = trimmed.indexOf("=");
    if (equalsIndex === -1) {
      continue;
    }
    const key = trimmed.slice(0, equalsIndex).trim();
    let value = trimmed.slice(equalsIndex + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

function validateConfig(config) {
  const required = [
    "OSS_AK",
    "OSS_SK",
    "OSS_ENDPOINT",
    "OSS_BUCKET",
    "OSS_HOST",
  ];
  const missing = required.filter((key) => !config[key]);
  if (missing.length > 0) {
    throw new Error(`Missing required env vars: ${missing.join(", ")}`);
  }
}

function contentTypeForPath(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  return IMAGE_TYPES.get(extension) || "application/octet-stream";
}

function sanitizeSlug(value) {
  return String(value || "image")
    .trim()
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "image";
}

function trimSlashes(value) {
  return String(value || "").replace(/^\/+|\/+$/g, "");
}

function joinUrl(baseUrl, key) {
  return `${String(baseUrl).replace(/\/+$/g, "")}/${trimSlashes(key)}`;
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function timestamp() {
  const date = new Date();
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join("");
}

function buildObjectKey(options, body) {
  const extension = path.extname(options.image).toLowerCase() || ".png";
  const hash = crypto.createHash("sha1").update(body).digest("hex").slice(0, 8);
  const fileName = `${sanitizeSlug(options.name)}-${timestamp()}-${hash}${extension}`;
  const prefix = trimSlashes(options.prefix);
  return prefix ? `${prefix}/${fileName}` : fileName;
}

function normalizeEndpoint(endpoint) {
  const value = endpoint.startsWith("http://") || endpoint.startsWith("https://")
    ? endpoint
    : `https://${endpoint}`;
  const parsed = new URL(value);
  if (parsed.protocol !== "https:") throw new Error("OSS endpoint must use HTTPS");
  return {
    protocol: parsed.protocol,
    hostname: parsed.hostname,
  };
}

function encodeObjectKey(objectKey) {
  return objectKey
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

function ossAuthorization(options) {
  const canonicalizedResource = `/${options.bucket}/${options.objectKey}`;
  const stringToSign = [
    options.method,
    "",
    options.contentType,
    options.date,
    canonicalizedResource,
  ].join("\n");
  const signature = crypto
    .createHmac("sha1", options.accessKeySecret)
    .update(stringToSign)
    .digest("base64");
  return `OSS ${options.accessKeyId}:${signature}`;
}

function putOssObject(options) {
  const endpoint = normalizeEndpoint(options.endpoint);
  const objectPath = `/${encodeObjectKey(options.objectKey)}`;
  const hostname = `${options.bucket}.${endpoint.hostname}`;
  const date = new Date().toUTCString();
  const headers = {
    Date: date,
    "Content-Type": options.contentType,
    "Content-Length": options.body.length,
    Authorization: ossAuthorization({
      method: "PUT",
      bucket: options.bucket,
      objectKey: options.objectKey,
      accessKeyId: options.accessKeyId,
      accessKeySecret: options.accessKeySecret,
      date,
      contentType: options.contentType,
    }),
  };

  return new Promise((resolve, reject) => {
    const request = https.request({
      method: "PUT",
      protocol: endpoint.protocol,
      hostname,
      path: objectPath,
      headers,
    }, (response) => {
      response.resume();
      response.on("end", () => {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve();
          return;
        }
        reject(new Error(`OSS upload failed with HTTP ${response.statusCode}`));
      });
    });
    request.setTimeout(30000, () => request.destroy(new Error("OSS upload timed out")));
    request.on("error", reject);
    request.write(options.body);
    request.end();
  });
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }
  if (!options.image) {
    throw new Error("--image is required");
  }
  if (!fs.existsSync(options.image)) {
    throw new Error(`Image file not found: ${options.image}`);
  }

  const body = fs.readFileSync(options.image);
  if (body.length === 0) {
    throw new Error("Image file is empty");
  }

  const config = loadEnv(options.envFile);
  validateConfig(config);

  const contentType = contentTypeForPath(options.image);
  const objectKey = buildObjectKey(options, body);
  const cdnUrl = joinUrl(config.OSS_HOST, objectKey);
  const result = {
    cdnUrl,
    objectKey,
    contentType,
    bytes: body.length,
    uploaded: !options.dryRun,
  };

  if (!options.dryRun) {
    await putOssObject({
      endpoint: config.OSS_ENDPOINT,
      bucket: config.OSS_BUCKET,
      accessKeyId: config.OSS_AK,
      accessKeySecret: config.OSS_SK,
      objectKey,
      body,
      contentType,
    });
  }

  if (options.json) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log(cdnUrl);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
