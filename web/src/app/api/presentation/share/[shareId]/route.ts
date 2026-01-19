import { NextRequest, NextResponse } from 'next/server';
import { logger } from '@/lib/server-logger';

// GET /api/pagtive/share/[shareId] - 获取分享项目的公开信息（无需认证）
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ shareId: string }> }
) {
  try {
    const { shareId } = await params;
    // 分享接口不需要认证，直接请求后端
    const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:6066/api';
    const response = await fetch(`${apiUrl}/webapps/pagtive/share/${shareId}/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(
        { error: error.message || '获取分享项目失败' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    logger.error('获取分享项目错误:', error);
    return NextResponse.json(
      { error: '服务器错误' },
      { status: 500 }
    );
  }
}