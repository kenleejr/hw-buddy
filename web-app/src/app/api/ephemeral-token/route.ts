import { NextRequest, NextResponse } from 'next/server';
import { GoogleGenAI } from '@google/genai';

export async function POST(request: NextRequest) {
  try {
    const apiKey = process.env.GEMINI_API_KEY;
    
    if (!apiKey) {
      return NextResponse.json(
        { error: 'GEMINI_API_KEY not configured' },
        { status: 500 }
      );
    }

    const client = new GoogleGenAI({ apiKey });
    const expireTime = new Date(Date.now() + 30 * 60 * 1000).toISOString();

    const token = await client.authTokens.create({
      config: {
        uses: 1,
        expireTime: expireTime,
        newSessionExpireTime: new Date(Date.now() + (1 * 60 * 1000)).toISOString(),
        httpOptions: { apiVersion: 'v1alpha' },
      },
    });

    console.log('Generated token:', token);
    console.log('Token name:', token.name);
    
    // Manually serialize the token object to ensure it's properly sent
    const tokenData = {
      name: token.name
    };

    return NextResponse.json({ token: tokenData });
    
  } catch (error: any) {
    console.error('Error generating ephemeral token:', error);
    return NextResponse.json(
      { error: `Failed to generate ephemeral token: ${error.message}` },
      { status: 500 }
    );
  }
}