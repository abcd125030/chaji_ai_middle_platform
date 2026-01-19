/**
 * Query payment order status API route
 * Proxy request to backend to check payment status
 */

import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';
import { logger } from '@/lib/server-logger';

export async function POST(request: NextRequest) {
  try {
    // Simply proxy the request to backend
    return proxyToBackend(request, '/payment/orders/query_status/');
    
  } catch (error) {
    logger.error('Failed to query payment status:', error);
    return NextResponse.json(
      { 
        status: 'error', 
        error: 'Failed to query payment status',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}