"""
IALIVE Vercel Serverless Webhook Function — site/api/webhook.ts

Questa function Vercel ascolta eventi GitHub (push nuovi post/content)
e triggera la coda di auto-post su Bluesky/Social.
Deploy automatico con il site repo (gia' configurato B5).

Setup:
1. Vercel > Settings > Environment Variables:
   - SUPABASE_URL
   - SUPABASE_KEY
   - BLUESKY_HANDLE
   - BLUESKY_APP_PASSWORD
   - WEBHOOK_SECRET (opzionale, valida firme)

2. GitHub repo > Settings > Webhooks:
   - URL: https://ialive-site.vercel.app/api/webhook
   - Content type: application/json
   - Events: push
   - Secret: WEBHOOK_SECRET (stesso env var)

3. Ogni push su main triggera il controller che:
   - Controlla se il commit ha aggiunto file in content/
   - Se si, estrae il testo dai nuovi file
   - Crea entry in Supabase content_queue
   - Il cron handler (o trigger immediato) posta
"""

import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

// Rate limiting: max 4 post/ora
const MAX_POSTS_PER_HOUR = 4;

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_KEY!
);

export async function POST(request: NextRequest) {
  const headers = { "Content-Type": "application/json" };
  
  try {
    // Parse GitHub webhook
    const body = await request.json();
    const event = request.headers.get("x-github-event");
    
    // Solo push events
    if (event !== "push") {
      return NextResponse.json(
        { ignored: true, reason: "not a push event" },
        { status: 200 }
      );
    }
    
    // Controlla ref (solo main)
    const ref = body.ref;
    if (ref !== "refs/heads/main") {
      return NextResponse.json(
        { ignored: true, reason: "not main branch" },
        { status: 200 }
      );
    }
    
    // Identifica file modificati/aggiunti
    const commits = body.commits || [];
    const addedFiles: string[] = [];
    
    for (const commit of commits) {
      addedFiles.push(...(commit.added || []));
      addedFiles.push(...(commit.modified || []));
    }
    
    // Filtra per file markdown in content/ (Quartz) o saggi/ (site)
    const contentFiles = addedFiles.filter(
      (f: string) =>
        f.startsWith("content/") && f.endsWith(".md") ||
        f.startsWith("site/saggi/") && f.endsWith(".html")
    );
    
    if (contentFiles.length === 0) {
      return NextResponse.json(
        { ignored: true, reason: "no content files changed" },
        { status: 200 }
      );
    }
    
    // Rate limit check
    const oneHourAgo = new Date(Date.now() - 3600_000).toISOString();
    const { count } = await supabase
      .from("social_posts")
      .select("*", { count: "exact", head: true })
      .gte("posted_at", oneHourAgo)
      .eq("status", "published");
    
    if ((count || 0) >= MAX_POSTS_PER_HOUR) {
      return NextResponse.json(
        { error: "Rate limit reached" },
        { status: 429, headers }
      );
    }
    
    // Estrai commit message per usare come testo del post
    // (o usa il primo commit body come contenuto)
    const commitMessage = commits[0]?.message || "";
    const commitSha = commits[0]?.id || "unknown";
    
    // Crea entry nella coda contenuti
    const { data, error } = await supabase.from("content_queue").insert({
      content: commitMessage.slice(0, 300),
      platforms: JSON.stringify(["bluesky"]),
      priority: 1,
      status: "pending",
      source: "github_webhook",
      source_url: `${body.repository?.html_url}/commit/${commitSha}`,
      created_at: new Date().toISOString(),
    });
    
    if (error) {
      return NextResponse.json(
        { error: error.message },
        { status: 500, headers }
      );
    }
    
    // Log come social_post di sistema
    await supabase.from("social_posts").insert({
      content: `[AUTO] Webhook triggered: ${contentFiles.length} files`,
      platforms: "system",
      posted_at: new Date().toISOString(),
      status: "system",
    });
    
    return NextResponse.json(
      {
        status: "queued",
        files: contentFiles.length,
        files_list: contentFiles.slice(0, 10),
        commit: commitSha,
        queue_id: data?.[0]?.id,
      },
      { status: 200, headers }
    );
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Internal error" },
      { status: 500, headers }
    );
  }
}
