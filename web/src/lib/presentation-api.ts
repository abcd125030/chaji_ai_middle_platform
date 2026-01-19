// Presentation API 客户端
// 封装所有与 Presentation 相关的 API 调用

interface Project {
  id: string;
  project_name: string;
  project_description?: string;
  project_style?: string;
  global_style_code?: string;
  pages?: unknown[];
  is_public?: boolean;
  is_published?: boolean;
  created_at?: string;
  updated_at?: string;
}

interface Page {
  id: number;
  title: string;
  order: number;
  html?: string;
  styles?: string;
  script?: string;
  mermaid_content?: string;
}

interface GenerateRequest {
  projectId: string;
  pageId?: string;
  prompt: string;
  template?: 'generatePageCode' | 'editPageCode';
  shortcuts?: string[];
  images?: unknown[];
  references?: unknown[];
  current?: {
    html?: string;
    styles?: string;
    script?: string;
    currentMermaid?: string;
  };
}

interface GenerateResponse {
  success: boolean;
  data?: {
    html: string;
    styles: string;
    script: string;
    mermaidContent?: string;
  };
  error?: string;
}

class PresentationAPI {
  private baseUrl = '/api/presentation';

  // 项目管理
  async getProjects(): Promise<Project[]> {
    const response = await fetch(`${this.baseUrl}/projects`);
    if (!response.ok) {
      throw new Error('获取项目列表失败');
    }
    return response.json();
  }

  async getProject(projectId: string): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}`);
    if (!response.ok) {
      throw new Error('获取项目详情失败');
    }
    return response.json();
  }

  async createProject(project: Partial<Project>): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(project),
    });
    if (!response.ok) {
      throw new Error('创建项目失败');
    }
    return response.json();
  }

  async updateProject(projectId: string, updates: Partial<Project>): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });
    if (!response.ok) {
      throw new Error('更新项目失败');
    }
    return response.json();
  }

  async deleteProject(projectId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('删除项目失败');
    }
  }

  // 页面管理
  async getPages(projectId: string): Promise<Page[]> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}/pages`);
    if (!response.ok) {
      throw new Error('获取页面列表失败');
    }
    return response.json();
  }

  async getPage(projectId: string, pageId: string): Promise<Page> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}/pages/${pageId}`);
    if (!response.ok) {
      throw new Error('获取页面详情失败');
    }
    return response.json();
  }

  async createPage(projectId: string, page: Partial<Page>): Promise<Page> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}/pages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(page),
    });
    if (!response.ok) {
      throw new Error('创建页面失败');
    }
    return response.json();
  }

  async updatePage(projectId: string, pageId: string, updates: Partial<Page>): Promise<Page> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}/pages/${pageId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });
    if (!response.ok) {
      throw new Error('更新页面失败');
    }
    return response.json();
  }

  async deletePage(projectId: string, pageId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/projects/${projectId}/pages/${pageId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('删除页面失败');
    }
  }

  // AI 生成
  async generate(request: GenerateRequest): Promise<GenerateResponse> {
    const response = await fetch(`${this.baseUrl}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'AI生成失败');
    }
    return response.json();
  }

  async generateOutline(projectDescription: string): Promise<unknown> {
    const response = await fetch(`${this.baseUrl}/generate/outline`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ description: projectDescription }),
    });
    if (!response.ok) {
      throw new Error('生成大纲失败');
    }
    return response.json();
  }

  // 分享功能
  async getSharedProject(shareId: string): Promise<Project> {
    const response = await fetch(`${this.baseUrl}/share/${shareId}`);
    if (!response.ok) {
      throw new Error('获取分享项目失败');
    }
    return response.json();
  }

  // 图片上传
  async uploadImage(file: File): Promise<{ url: string }> {
    const formData = new FormData();
    formData.append('image', file);
    
    const response = await fetch(`${this.baseUrl}/upload/image`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error('上传图片失败');
    }
    return response.json();
  }
}

// 导出单例
export const presentationAPI = new PresentationAPI();

// 导出类型
export type { Project, Page, GenerateRequest, GenerateResponse };