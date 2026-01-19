import { NextRequest, NextResponse } from 'next/server';
import { jwtDecode } from 'jwt-decode';
import { z } from 'zod';
import { proxyToBackend } from '@/lib/backend-proxy';
import { logger } from '@/lib/server-logger';

const jwtPayloadSchema = z.object({
  user_id: z.preprocess((val) => String(val), z.string()),
});

export async function POST(request: NextRequest) {
  try {
    const authHeader = request.headers.get('Authorization');

    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return NextResponse.json(
        { error: 'Authorization header is required' },
        { status: 401 },
      );
    }

    const accessToken = authHeader.split(' ')[1];

    let decoded: unknown;
    try {
      decoded = jwtDecode(accessToken);
    } catch {
      return NextResponse.json({ error: 'Invalid access token' }, { status: 401 });
    }

    const validationResult = jwtPayloadSchema.safeParse(decoded);

    if (!validationResult.success) {
      return NextResponse.json(
        { error: 'Invalid token payload', details: validationResult.error.flatten() },
        { status: 401 },
      );
    }
    
    const { user_id: userId } = validationResult.data;
    logger.info('Decoded user ID:', userId);
    
    // 使用 proxyToBackend 调用后端 API
    try {
      const response = await proxyToBackend(request, '/auth/profile/');
      
      if (!response.ok) {
        if (response.status === 404) {
          return NextResponse.json({ error: 'User not found' }, { status: 404 });
        }
        // 如果后端不可用，返回默认角色
        logger.error('Backend API error:', response.status);
        return NextResponse.json({ role: 'user' });
      }

      const responseData = await response.json();
      logger.info('Backend response:', JSON.stringify(responseData, null, 2));
      
      // 从后端响应中提取角色信息
      // 后端返回的数据结构是 { user: {...}, feishu: {...}, last_login: ... }
      const userData = responseData.user || responseData;
      const role = userData.role || (userData.is_staff ? 'admin' : 'user');
      
      logger.info('User data:', userData);
      logger.info('Determined role:', role);
      
      return NextResponse.json({ role });
    } catch (backendError) {
      logger.error('Error calling backend API:', backendError);
      // 如果后端不可用，返回默认角色
      return NextResponse.json({ role: 'user' });
    }

  } catch (error) {
    logger.error('Error verifying user role:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}