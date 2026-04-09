export type Genre =
  | "fantasy"
  | "science_fiction"
  | "mystery"
  | "thriller"
  | "romance"
  | "horror"
  | "literary"
  | "historical"
  | "young_adult"
  | "xuanhuan"
  | "xianxia"
  | "chuanyue"
  | "chongsheng"
  | "dushi"
  | "xitong"
  | "gongdou"
  | "moshi"
  | "wuxia"
  | "yanqing"
  | "danmei"
  | "junshi";

export type NarrativeStructure =
  | "three_act"
  | "heros_journey"
  | "save_the_cat"
  | "kishotenketsu"
  | "freytags_pyramid"
  | "shengji"
  | "fucho"
  | "shuangwen"
  | "qifu";

export type WritingStyle =
  | "literary"
  | "commercial"
  | "minimalist"
  | "ornate"
  | "dialogue_heavy"
  | "action_paced"
  | "introspective"
  | "shuangkuai"
  | "xijie"
  | "qingsong"
  | "rexue"
  | "nuexin"
  | "guyan"
  | "zhichang";

export type POV = "first_person" | "third_limited" | "third_omniscient";

export interface CharacterBrief {
  name: string;
  role: string;
  description: string;
  motivation: string;
}

export interface NovelRequest {
  premise: string;
  genre: Genre;
  structure: NarrativeStructure;
  style: WritingStyle;
  pov: POV;
  target_chapters: number;
  characters: CharacterBrief[];
  setting_notes: string;
  theme_notes: string;
  tone: string;
}

export interface StreamMessage {
  type: string;
  agent?: string;
  content?: string;
  data?: Record<string, unknown>;
  novel_id?: string;
  chapter?: number;
  word_count?: number;
}

export interface AuthState {
  isAuthenticated: boolean;
  idToken: string | null;
  email: string | null;
}

export type NovelStatus = "chat" | "step1_draft" | "step1_done" | "step2_draft" | "step2_done" | "writing" | "completed";

export type PageView = "home" | "composer" | "chat";

export interface NovelSummary {
  novel_id: string;
  user_id: string;
  status: NovelStatus;
  premise?: string;
  created_at?: number;
  title?: string;
}

export interface NovelState {
  novel_id: string;
  user_id?: string;
  status: NovelStatus;
  premise?: string;
  created_at?: number;
  title?: string;
  structure?: string;
  characters?: string;
  world?: string;
  plot?: string;
  chat_history?: Array<{ role: string; content: string }>;
  chapters?: Record<number, string>;  // {1: "content", 2: "content"}
}

export interface UserMemory {
  user_preferences: {
    preferred_style?: string;
    preferred_genre?: string;
    notes?: string;
  };
  current_novel: {
    novel_id?: string;
    title?: string;
    key_characters?: string[];
    plot_summary?: string;
    world_summary?: string;
    chapters_written?: number[];
  };
  chat_history_summary?: string;
  updated_at?: number;
}
