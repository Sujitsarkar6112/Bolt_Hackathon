#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

console.log('🚀 Starting Enhanced DemandBot System');
console.log('=====================================');

// Update environment configuration
const envPath = path.join(__dirname, '.env');
let envContent = fs.readFileSync(envPath, 'utf8');

// Update WebSocket URL to enhanced backend
envContent = envContent.replace(
  'VITE_WS_URL=ws://localhost:8004/chat',
  'VITE_WS_URL=ws://localhost:8005/chat'
);
envContent = envContent.replace(
  'VITE_API_URL=http://localhost:8000',
  'VITE_API_URL=http://localhost:8005'
);

fs.writeFileSync(envPath, envContent);
console.log('✅ Updated environment configuration for enhanced backend');

// Check if enhanced backend is running
exec('curl -s http://localhost:8005/health', (error, stdout, stderr) => {
  if (error) {
    console.log('❌ Enhanced backend not running. Please start it with:');
    console.log('   cd backend && python app/enhanced_main.py');
    console.log('');
    console.log('🔥 Enhanced Features:');
    console.log('   • Real sales data analysis (1,000 transactions)');
    console.log('   • Direct OpenAI GPT-3.5 integration');
    console.log('   • AI-enhanced forecasting');
    console.log('   • Strategic business insights');
    console.log('   • WebSocket real-time chat');
    return;
  }

  try {
    const health = JSON.parse(stdout);
    console.log(`✅ Enhanced backend status: ${health.status}`);
    console.log(`📊 Database: ${health.database_status}`);
    console.log(`🤖 OpenAI: ${health.openai_connected ? 'Connected' : 'Disconnected'}`);
    console.log(`📈 Version: ${health.version}`);
    console.log('');
    
    if (health.openai_connected) {
      console.log('🎉 FULL AI INTEGRATION ACTIVE!');
      console.log('   • Real data + AI insights combined');
      console.log('   • Strategic recommendations powered by GPT-3.5');
      console.log('   • Enhanced forecasting with AI analysis');
    } else {
      console.log('⚠️  AI integration unavailable - data analysis only');
    }
  } catch (e) {
    console.log('⚠️  Backend running but status unclear');
  }
});

console.log('');
console.log('🌐 Frontend will connect to: http://localhost:5173');
console.log('🔌 WebSocket endpoint: ws://localhost:8005/chat');
console.log('📡 API endpoint: http://localhost:8005');
console.log('');
console.log('💡 Try these enhanced queries:');
console.log('   • "What strategic insights do you have for Electronics?"');
console.log('   • "Give me AI-powered recommendations for Beauty products"');
console.log('   • "How can I improve my business performance?"');
console.log('   • "Should I invest more in Clothing or Electronics?"'); 