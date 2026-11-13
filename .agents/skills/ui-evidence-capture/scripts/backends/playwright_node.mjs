#!/usr/bin/env node
/**
 * playwright_node.mjs - Playwright Node.js Backend for UI Evidence Capture.
 * Reads JSON payload from stdin, executes browser actions, and outputs JSON to stdout.
 */

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { URL } from 'node:url';

// Parse command and read payload
const command = process.argv[2] || 'shot';

let inputData = '';
process.stdin.setEncoding('utf8');

process.stdin.on('data', (chunk) => {
  inputData += chunk;
});

process.stdin.on('end', async () => {
  try {
    let payload = {};
    if (inputData.trim()) {
      payload = JSON.parse(inputData);
    }

    if (command === 'detect') {
      await handleDetect();
    } else if (command === 'shot') {
      await handleShot(payload);
    } else if (command === 'login') {
      await handleLogin(payload);
    } else {
      console.log(JSON.stringify({ exit_code: 40, error: `Unknown command: ${command}` }));
      process.exit(0);
    }
  } catch (err) {
    console.log(JSON.stringify({ exit_code: 50, error: err.message }));
    process.exit(0);
  }
});

async function handleDetect() {
  try {
    const { chromium } = await import('playwright');
    console.log(JSON.stringify({ exit_code: 0, status: 'ready', type: 'playwright-node' }));
  } catch (e) {
    console.log(JSON.stringify({ exit_code: 11, status: 'not_installed', error: e.message }));
  }
}

async function handleLogin(payload) {
  const { login_url, session_path, post_login_selector } = payload;
  if (!login_url) {
    console.log(JSON.stringify({ exit_code: 40, error: 'login_url is required' }));
    return;
  }

  let playwrightModule;
  try {
    playwrightModule = await import('playwright');
  } catch (e) {
    console.log(JSON.stringify({ exit_code: 11, error: 'Playwright node module not found' }));
    return;
  }

  const { chromium } = playwrightModule;
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.error(`[*] Navigating to ${login_url} for human login...`);
  await page.goto(login_url);

  if (post_login_selector) {
    console.error(`[*] Waiting for post-login selector: ${post_login_selector}...`);
    try {
      await page.waitForSelector(post_login_selector, { timeout: 180000 });
    } catch (e) {
      await browser.close();
      console.log(JSON.stringify({ exit_code: 20, error: 'Login timeout or failed' }));
      return;
    }
  } else {
    console.error('[*] Please complete login in browser. Waiting 30s...');
    await new Promise((r) => setTimeout(r, 30000));
  }

  fs.mkdirSync(path.dirname(session_path), { recursive: true });
  await context.storageState({ path: session_path });
  fs.chmodSync(session_path, 0o600);
  await browser.close();

  console.log(JSON.stringify({ exit_code: 0, status: 'saved', session_path }));
}

async function handleShot(payload) {
  const {
    url,
    output_path,
    session_path,
    vw = 1440,
    vh = 900,
    full_page = true,
    mask = [],
    wait_for,
    allowed_origins = [],
    allow_mutation_paths = [],
    login_url
  } = payload;

  let playwrightModule;
  try {
    playwrightModule = await import('playwright');
  } catch (e) {
    console.log(JSON.stringify({ exit_code: 11, error: 'Playwright node module not found' }));
    return;
  }

  const { chromium } = playwrightModule;
  const browser = await chromium.launch({ headless: true });
  const contextOptions = { viewport: { width: Number(vw), height: Number(vh) } };

  if (session_path && fs.existsSync(session_path)) {
    contextOptions.storageState = session_path;
  }

  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();

  let blocked_mutation_count = 0;

  await page.route('**/*', (route) => {
    const req = route.request();
    const reqUrl = req.url();
    try {
      const parsed = new URL(reqUrl);
      const origin = `${parsed.protocol}//${parsed.host}`;

      if (allowed_origins.length > 0 && !allowed_origins.includes(origin)) {
        route.abort();
        return;
      }

      if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method())) {
        if (!allow_mutation_paths.includes(reqUrl) && !allow_mutation_paths.includes(parsed.pathname)) {
          blocked_mutation_count += 1;
          route.abort();
          return;
        }
      }
      route.continue();
    } catch {
      route.abort();
    }
  });

  let response;
  try {
    response = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  } catch (err) {
    const currentUrl = page.url();
    if (login_url && currentUrl.startsWith(login_url)) {
      await browser.close();
      console.log(JSON.stringify({ exit_code: 20, error: 'AUTH_REQUIRED', currentUrl }));
      return;
    }
    await browser.close();
    console.log(JSON.stringify({ exit_code: 50, error: err.message }));
    return;
  }

  const currentUrl = page.url();
  if (response && [401, 403].includes(response.status())) {
    await browser.close();
    console.log(JSON.stringify({ exit_code: 20, error: 'AUTH_REQUIRED', status: response.status() }));
    return;
  }

  if (login_url && currentUrl.startsWith(login_url) && !url.startsWith(login_url)) {
    await browser.close();
    console.log(JSON.stringify({ exit_code: 20, error: 'AUTH_REQUIRED', currentUrl }));
    return;
  }

  // Challenge detection
  const content = await page.content();
  const lowerContent = content.toLowerCase();
  const challengeKeywords = [
    'recaptcha', 'hcaptcha', 'challenges.cloudflare.com', 'cf-turnstile',
    'verify you are human', 'checking your browser', 'security check',
    'human verification', 'bot detection', 'two-factor authentication', 'enter otp'
  ];

  if (challengeKeywords.some((k) => lowerContent.includes(k))) {
    await browser.close();
    console.log(JSON.stringify({ exit_code: 21, error: 'HUMAN_CHALLENGE' }));
    return;
  }

  if (wait_for) {
    try {
      await page.waitForSelector(wait_for, { timeout: 10000 });
    } catch {
      // continue anyway
    }
  }

  // Masking
  const maskLocators = [];
  for (const sel of mask) {
    try {
      maskLocators.push(page.locator(sel));
    } catch {}
  }

  fs.mkdirSync(path.dirname(output_path), { recursive: true });
  await page.screenshot({
    path: output_path,
    fullPage: full_page,
    mask: maskLocators
  });

  await browser.close();

  console.log(JSON.stringify({
    exit_code: 0,
    blocked_mutations: blocked_mutation_count
  }));
}
