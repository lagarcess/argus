export type Mention = {
  id: string;
  type: string;
  label: string;
  insert_text: string;
  description?: string | null;
  symbol?: string | null;
  provider?: string | null;
  message_range?: { start: number; end: number };
};
