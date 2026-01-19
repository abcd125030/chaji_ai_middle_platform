import { NextRequest } from 'next/server';
import { proxyToBackend, handleOptions } from '@/lib/backend-proxy';

/**
 * API Key detail endpoints
 * PATCH: Update API key name
 * DELETE: Delete API key
 */

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyToBackend(request, `/service/api-keys/${id}/`);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyToBackend(request, `/service/api-keys/${id}/`);
}

export async function OPTIONS() {
  return handleOptions();
}
