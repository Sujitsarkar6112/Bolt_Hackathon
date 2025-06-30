import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = join(__dirname, '..');

const services = [
  {
    name: 'Frontend',
    command: 'npm',
    args: ['run', 'dev'],
    cwd: projectRoot,
    color: '\x1b[36m' // Cyan
  }
];

// Only start Python services if Python is available
const pythonServices = [
  {
    name: 'Gateway',
    command: 'python3',
    args: ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8004'],
    cwd: join(projectRoot, 'gateway_service'),
    color: '\x1b[32m' // Green
  },
  {
    name: 'RAG Service',
    command: 'python3',
    args: ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8001'],
    cwd: join(projectRoot, 'rag_service'),
    color: '\x1b[33m' // Yellow
  },
  {
    name: 'Forecast Service',
    command: 'python3',
    args: ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8002'],
    cwd: join(projectRoot, 'forecast_service'),
    color: '\x1b[35m' // Magenta
  }
];

function startService(service) {
  console.log(`${service.color}Starting ${service.name}...\x1b[0m`);
  
  const process = spawn(service.command, service.args, {
    cwd: service.cwd,
    stdio: 'pipe',
    shell: true
  });

  process.stdout.on('data', (data) => {
    console.log(`${service.color}[${service.name}]\x1b[0m ${data.toString().trim()}`);
  });

  process.stderr.on('data', (data) => {
    console.error(`${service.color}[${service.name} ERROR]\x1b[0m ${data.toString().trim()}`);
  });

  process.on('close', (code) => {
    console.log(`${service.color}[${service.name}]\x1b[0m Process exited with code ${code}`);
  });

  return process;
}

// Start all services
const processes = [];

// Always start frontend
services.forEach(service => {
  processes.push(startService(service));
});

// Check if Python is available before starting Python services
spawn('python3', ['--version'], { stdio: 'pipe' })
  .on('close', (code) => {
    if (code === 0) {
      console.log('\x1b[32mPython detected, starting backend services...\x1b[0m');
      pythonServices.forEach(service => {
        processes.push(startService(service));
      });
    } else {
      console.log('\x1b[33mPython not available, running frontend only...\x1b[0m');
    }
  });

// Handle graceful shutdown
process.on('SIGINT', () => {
  console.log('\n\x1b[31mShutting down services...\x1b[0m');
  processes.forEach(proc => {
    if (proc && !proc.killed) {
      proc.kill('SIGTERM');
    }
  });
  process.exit(0);
});

console.log('\x1b[36mService manager started. Press Ctrl+C to stop all services.\x1b[0m');