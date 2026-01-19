import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

/**
 * API Key management endpoints
 * GET: List all API keys for current user
 * POST: Create a new API key
 */

export async function GET(request: NextRequest) {
  return proxyToBackend(request, '/service/api-keys/');
}

export async function POST(request: NextRequest) {
  return proxyToBackend(request, '/service/api-keys/');
}

export async function OPTIONS() {
  return handleOptions();
}
