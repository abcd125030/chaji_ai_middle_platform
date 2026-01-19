/**
 * Cancel payment order API route
 * Proxy request to backend to cancel a payment order
 */

import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/backend-proxy';
import { logger } from '@/lib/server-logger';

export async function POST(request: NextRequest) {
  try {
    // Simply proxy the request to the new cancel_by_order_id endpoint
    // The body already contains order_id which is what the backend expects
    return proxyToBackend(request, '/payment/orders/cancel_by_order_id/');
    
  } catch (error) {
    logger.error('Failed to cancel payment order:', error);
    return NextResponse.json(
      { 
        status: 'error', 
        error: 'Failed to cancel order',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}