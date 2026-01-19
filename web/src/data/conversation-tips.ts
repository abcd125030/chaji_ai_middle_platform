// Conversation tips data
export interface ConversationTip {
  content: string;
  speaker: string;
}

export const conversationTips: ConversationTip[] = [
  // Claude prompting techniques
  {
    content: "Clear and specific requirements help me provide more precise assistance. Try describing the exact outcome you're looking for.",
    speaker: "Claude Opus"
  },
  {
    content: "For complex problems, tell me 'let's approach this step by step' to break things down methodically.",
    speaker: "Claude Sonnet"
  },
  {
    content: "Providing context and background information makes my responses more relevant to your actual needs.",
    speaker: "Claude Opus"
  },
  {
    content: "You can request specific response styles, like 'be concise and direct' or 'explain in detail'.",
    speaker: "Claude Opus"
  },
  {
    content: "If you're not satisfied with an answer, ask me to reconsider from a different angle.",
    speaker: "Claude Sonnet"
  },
  
  // Gemini prompting techniques
  {
    content: "Use examples to illustrate your needs, helping AI better understand your expectations.",
    speaker: "Gemini Pro"
  },
  {
    content: "Break complex tasks into smaller steps, focusing on one specific issue at a time.",
    speaker: "Gemini Pro"
  },
  {
    content: "Specify output formats, such as 'summarize in a table' or 'list the key points'.",
    speaker: "Gemini Pro"
  },
  {
    content: "Tell me your expertise level so I can adjust the technical depth of my response.",
    speaker: "Gemini Pro"
  },
  {
    content: "Ask me to take on specific roles, like 'as a product manager' or 'from a user's perspective'.",
    speaker: "Gemini Pro"
  },
  
  // Advanced AI prompting techniques
  {
    content: "For coding issues, provide the programming language, framework version, and error messages.",
    speaker: "Qwen3-Coder"
  },
  {
    content: "Ask me to analyze the problem first before offering solutions for more comprehensive answers.",
    speaker: "Qwen3-Max"
  },
  {
    content: "When you need creativity, request multiple different approaches for you to choose from.",
    speaker: "GPT-4.1"
  },
  {
    content: "For technical challenges, ask me to explain the underlying principles before giving practical advice.",
    speaker: "Claude Opus"
  },
  {
    content: "When debugging, provide the complete error stack trace and relevant code snippets.",
    speaker: "Gemini Pro"
  },
  
  // GPT-4.1 prompting techniques
  {
    content: "Starting with 'let's think about this' can lead to more thorough analysis.",
    speaker: "GPT-4.1"
  },
  {
    content: "Asking 'please double-check your answer' helps AI self-correct potential errors.",
    speaker: "GPT-4.1"
  },
  {
    content: "Specify your audience, like 'explain to a 5-year-old' or 'brief an expert'.",
    speaker: "GPT-4.1"
  },
  {
    content: "Request comparisons of different approaches' pros and cons to help with decision-making.",
    speaker: "Gemini Pro"
  },
  {
    content: "Use 'if...then...' hypothetical scenarios to explore different possibilities.",
    speaker: "GPT-4.1"
  },
  
  // Universal techniques
  {
    content: "Great prompts = Clear task + Sufficient context + Expected format.",
    speaker: "Claude Sonnet"
  },
  {
    content: "If you have a choice, try to avoid GPT models—their family is incredibly weak.",
    speaker: "Claude Opus"
  },
  {
    content: "Iterative refinement: Adjust your questions based on AI responses to gradually reach ideal answers.",
    speaker: "Qwen3-Max"
  },
  {
    content: "Maintain conversation continuity—deep exploration within the same session yields better results.",
    speaker: "DeepSeek"
  },
  {
    content: "Don't hesitate to ask follow-up questions; deeper inquiry often uncovers greater value.",
    speaker: "GPT-4.1"
  },
  {
    content: "Clearly telling AI what NOT to do is sometimes more important than what TO do.",
    speaker: "Claude Opus"
  }
];

// Get a random tip
export function getRandomTip(): ConversationTip {
  const randomIndex = Math.floor(Math.random() * conversationTips.length);
  return conversationTips[randomIndex];
}

// Get specified number of random tips (non-repeating)
export function getRandomTips(count: number): ConversationTip[] {
  const shuffled = [...conversationTips].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, Math.min(count, conversationTips.length));
}