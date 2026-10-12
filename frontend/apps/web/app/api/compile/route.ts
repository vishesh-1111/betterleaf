import { NextResponse } from "next/server";
import { compileRatelimit, getIP } from "@/lib/ratelimit";

export const maxDuration = 60;

interface CompileResource {
  path: string;
  content?: string;
  file?: string;
  main?: boolean;
}

export async function POST(req: Request) {
  if (compileRatelimit) {
    const ip = getIP(req);
    const { success, limit, remaining, reset } =
      await compileRatelimit.limit(ip);

    if (!success) {
      return NextResponse.json(
        { error: "Too many requests" },
        {
          status: 429,
          headers: {
            "X-RateLimit-Limit": limit.toString(),
            "X-RateLimit-Remaining": remaining.toString(),
            "X-RateLimit-Reset": reset.toString(),
          },
        },
      );
    }
  }

  try {
    const { resources } = (await req.json()) as {
      resources: CompileResource[];
    };

    if (!resources || resources.length === 0) {
      return NextResponse.json(
        { error: "No resources provided" },
        { status: 400 },
      );
    }

    // The betterleaf latex service (`POST /compile`) expects:
    //   { mainFile, files: [{ path, content: <base64> }] }
    // and responds with JSON: { status, log, pdf: <base64 | null> }.
    const mainResource =
      resources.find((r) => r.main) ??
      resources.find((r) => r.path.endsWith(".tex"));

    if (!mainResource) {
      return NextResponse.json(
        { error: "No main .tex file found" },
        { status: 400 },
      );
    }

    const files = resources.map((r) => {
      let content = r.content ?? "";

      const isBase64Image =
        r.content &&
        !r.file &&
        (r.content.startsWith("/9j/") || r.content.startsWith("iVBOR"));

      if (isBase64Image) {
        content = r.content.replace(/\s/g, "");
      } else if (r.file) {
        content = r.file.replace(/\s/g, "");
      } else if (r.content) {
        // Betterleaf expects base64-encoded UTF-8 content for text files.
        content = Buffer.from(r.content, "utf8").toString("base64");
      }

      return { path: r.path, content };
    });

    const latexApiUrl = process.env.LATEX_API_URL || "http://localhost:7030";
    const response = await fetch(`${latexApiUrl}/compile`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        mainFile: mainResource.path,
        files,
      }),
    });

    if (!response.ok) {
      let message = "Unknown compilation error";
      try {
        const errorData = (await response.json()) as { error?: string };
        message = errorData.error || message;
      } catch {
        // non-JSON error body; fall through with generic message
      }
      return NextResponse.json(
        { error: `Compilation failed: ${message}` },
        { status: 500 },
      );
    }

    const result = (await response.json()) as {
      status: number;
      log?: string;
      pdf?: string | null;
    };

    if (result.status !== 0 || !result.pdf) {
      const log = result.log ?? "";
      const errorLines = log
        .split("\n")
        .filter(
          (line: string) =>
            line.includes("Error") ||
            line.includes("!") ||
            line.includes("Missing"),
        )
        .slice(0, 10)
        .join("\n");
      return NextResponse.json(
        {
          error: `Compilation failed (status ${result.status})`,
          details: errorLines || log.slice(-1000),
        },
        { status: 500 },
      );
    }

    const pdfBuffer = Buffer.from(result.pdf, "base64");

    return new NextResponse(pdfBuffer, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": "inline; filename=document.pdf",
      },
    });
  } catch (error) {
    console.error("Compilation error:", error);
    return NextResponse.json(
      {
        error:
          error instanceof Error ? error.message : "Unknown compilation error",
      },
      { status: 500 },
    );
  }
}
