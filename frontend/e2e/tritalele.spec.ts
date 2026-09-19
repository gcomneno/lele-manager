import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

const API = "/api/v1/tritalele";

function ingestionRegion(page: Page) {
  return page.getByRole("region", {
    name: "Collect new LeLe",
    exact: true,
  });
}

async function countVaultFiles(page: Page): Promise<number> {
  const response = await page.request.get("/vault/tree");
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as {
    tree: { type: "dir" | "file"; children?: unknown[] };
  };
  const count = (node: unknown): number => {
    if (typeof node !== "object" || node === null) return 0;
    const item = node as { type?: string; children?: unknown[] };
    if (item.type === "file") return 1;
    return (item.children ?? []).reduce<number>(
      (total, child) => total + count(child),
      0,
    );
  };
  return count(body.tree);
}

async function stageAccepted(
  request: APIRequestContext,
  logicalName: string,
): Promise<{
  candidateId: string;
  revision: number;
  lessonId: string;
  path: string;
}> {
  const staged = await request.post(`${API}/ingestion/stage`, {
    data: {
      content: `Candidate for controlled partial refresh: ${logicalName}`,
      source_kind: "plain_text",
      logical_name: logicalName,
      max_characters: 2000,
    },
  });
  expect(staged.ok()).toBeTruthy();
  const candidateId = (await staged.json()).candidate_ids[0] as string;
  const revised = await request.patch(
    `${API}/candidates/${encodeURIComponent(candidateId)}`,
    {
      data: {
        expected_revision: 0,
        proposed_metadata: {
          topic: "e2e",
          source: "playwright",
          importance: 4,
          tags: ["e2e", "partial"],
          date: "2026-07-22",
          title: "Controlled partial refresh",
        },
      },
    },
  );
  expect(revised.ok()).toBeTruthy();
  const revisedBody = await revised.json();
  const accepted = await request.post(
    `${API}/candidates/${encodeURIComponent(candidateId)}/accept`,
    {
      data: {
        expected_revision: revisedBody.revision,
        reason: "ready for controlled E2E",
      },
    },
  );
  expect(accepted.ok()).toBeTruthy();
  const acceptedBody = await accepted.json();
  return {
    candidateId,
    revision: acceptedBody.revision,
    lessonId: acceptedBody.approval_destination.lesson_id,
    path: acceptedBody.approval_destination.relative_vault_path,
  };
}

test.describe.serial("TritaLeLe GUI", () => {
  test("plain text: preview, stage, revise, accept and one explicit approval", async ({
    page,
  }) => {
    await page.goto("/app/#/tritalele");
    await expect(
      page.getByRole("heading", { name: "Collect new LeLe" }),
    ).toBeVisible();
    await expect(page.getByText("No selection.")).toBeVisible();

    const initialVaultFiles = await countVaultFiles(page);

    await ingestionRegion(page)
      .getByLabel("Source name")
      .fill("pasted-happy-path.txt");
    const source = ingestionRegion(page).getByLabel("Source text");
    await source.fill(
      "Plain text incollato per il workflow TritaLeLe deterministico.",
    );
    await page.getByRole("button", { name: "Create preview" }).click();
    await expect(page.getByTestId("ingestion-preview")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Add to collection" }),
    ).toBeEnabled();

    await source.fill(
      "Plain text incollato modificato: la preview precedente non è più valida.",
    );
    await expect(page.getByTestId("ingestion-preview")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Add to collection" }),
    ).toBeDisabled();

    await page.getByRole("button", { name: "Create preview" }).click();
    await page.getByRole("button", { name: "Add to collection" }).click();
    await expect(page.getByText(/Staging completed/)).toBeVisible();
    expect(await countVaultFiles(page)).toBe(initialVaultFiles);

    await page
      .locator(".candidate-card")
      .filter({ hasText: "pasted-happy-path.txt" })
      .click();
    await expect(
      page.getByRole("heading", { name: "LeLe details" }),
    ).toBeVisible();
    await page
      .getByLabel("Proposed text")
      .fill(
        "Testo rivisto in Markdown con **contenuto canonico** e provenienza intatta.",
      );
    await page.getByLabel("Topic", { exact: true }).fill("e2e");
    await page.getByLabel("Source", { exact: true }).fill("playwright");
    await page.getByLabel("Importance", { exact: true }).fill("4");
    await page.getByLabel("Date", { exact: true }).fill("2026-07-22");
    await page.getByLabel("Tags", { exact: true }).fill("e2e, tritalele");
    await page.getByLabel("Title", { exact: true }).fill("TritaLeLe approval");
    await page.getByLabel("Revision reason (optional)").fill("editorial pass");
    await page.getByRole("button", { name: "Save revision" }).click();
    await expect(page.getByText(/Revision 1 saved/)).toBeVisible();
    await expect(page.getByTestId("approval-destination")).toContainText(
      "e2e/",
    );
    expect(await countVaultFiles(page)).toBe(initialVaultFiles);

    await page.getByLabel(/Transition reason/).fill("ready");
    await page.getByRole("button", { name: "Accept for review" }).click();
    await expect(page.getByText(/is not published yet/)).toBeVisible();
    expect(await countVaultFiles(page)).toBe(initialVaultFiles);

    let approvalRequests = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/approve")) {
        approvalRequests += 1;
      }
    });
    await page.getByRole("button", { name: "Approve to vault" }).click();
    const dialog = page.getByRole("dialog", {
      name: "Confirm canonical approval",
    });
    await expect(dialog).toContainText("Candidate");
    await expect(dialog).toContainText("Revision");
    await expect(dialog).toContainText("Lesson ID");
    await expect(dialog).toContainText("Canonical path");
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toHaveCount(0);
    expect(approvalRequests).toBe(0);

    await page.getByRole("button", { name: "Approve to vault" }).click();
    await page.getByRole("button", { name: "Confirm approval" }).click();
    await expect(page.getByTestId("approval-result")).toContainText("created");
    await expect(page.getByText(/Lesson read back:/)).toBeVisible();
    await expect(page.getByText(/Vault file read back:/)).toBeVisible();
    expect(approvalRequests).toBe(1);
    expect(await countVaultFiles(page)).toBe(initialVaultFiles + 1);

    const lessons = await page.request.get("/lessons?limit=50");
    expect(lessons.ok()).toBeTruthy();
    expect(((await lessons.json()) as unknown[]).length).toBe(
      initialVaultFiles + 1,
    );
  });

  test("Markdown file can be staged and a rejected candidate remains visible", async ({
    page,
  }) => {
    await page.goto("/app/#/tritalele");
    const initialVaultFiles = await countVaultFiles(page);

    await ingestionRegion(page)
      .getByLabel("Markdown or text file")
      .setInputFiles({
        name: "file-input.md",
        mimeType: "text/markdown",
        buffer: Buffer.from("# File input\n\nCandidate rejected but retained."),
      });
    await expect(
      ingestionRegion(page).getByLabel("Content format"),
    ).toHaveValue("markdown");
    await expect(ingestionRegion(page).getByLabel("Source name")).toHaveValue(
      "file-input.md",
    );
    await page.getByRole("button", { name: "Create preview" }).click();
    await expect(page.getByTestId("ingestion-preview")).toBeVisible();
    await page.getByRole("button", { name: "Add to collection" }).click();
    await expect(page.getByText(/Staging completed/)).toBeVisible();

    await page
      .locator(".candidate-card")
      .filter({ hasText: "file-input.md" })
      .click();
    await page.getByLabel(/Transition reason/).fill("not useful for the vault");
    await page.getByRole("button", { name: "Reject candidate" }).click();
    await expect(page.getByText(/remains in staging/)).toBeVisible();
    await expect(
      page.locator(".candidate-card").filter({ hasText: "file-input.md" }),
    ).toBeVisible();
    await expect(page.getByText("Rejected → Rejected")).toHaveCount(0);
    await expect(page.getByText("Staged → Rejected")).toBeVisible();
    await expect(page.getByText("not useful for the vault")).toBeVisible();
    expect(await countVaultFiles(page)).toBe(initialVaultFiles);
  });

  test("409, 422, 503 and obsolete preview responses are controlled", async ({
    page,
  }) => {
    await page.goto("/app/#/tritalele");
    await ingestionRegion(page)
      .getByLabel("Source name")
      .fill("controlled-errors.txt");
    await ingestionRegion(page)
      .getByLabel("Source text")
      .fill("Valid input used to exercise controlled HTTP errors.");

    const previewUrl = "**/api/v1/tritalele/ingestion/preview";
    await page.route(previewUrl, (route) =>
      route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { code: "ingestion_conflict", message: "Conflict." },
        }),
      }),
    );
    await page.getByRole("button", { name: "Create preview" }).click();
    await expect(
      page.getByText(/Conflict \(409 · ingestion_conflict\)/),
    ).toBeVisible();
    await page.unroute(previewUrl);

    await page.route(previewUrl, (route) =>
      route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({
          detail: [{ loc: ["body"], msg: "invalid", type: "value_error" }],
        }),
      }),
    );
    await page.getByRole("button", { name: "Create preview" }).click();
    await expect(page.getByText(/Invalid data \(422\)/)).toBeVisible();
    await page.unroute(previewUrl);

    await page.route(previewUrl, (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            code: "candidate_storage_unavailable",
            message: "Unavailable.",
          },
        }),
      }),
    );
    await page.getByRole("button", { name: "Create preview" }).click();
    await expect(
      page.getByText(
        /Operational error \(503 · candidate_storage_unavailable\)/,
      ),
    ).toBeVisible();
    await page.unroute(previewUrl);

    await page.route(previewUrl, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 300));
      await route.continue();
    });
    await page.getByRole("button", { name: "Create preview" }).click();
    await ingestionRegion(page)
      .getByLabel("Source text")
      .fill("Changed while the preview request is still running.");
    await page.waitForTimeout(500);
    await expect(page.getByTestId("ingestion-preview")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Add to collection" }),
    ).toBeDisabled();
    await page.unroute(previewUrl);
  });

  test("partial_refresh is reported as persisted with separate read-backs", async ({
    page,
  }) => {
    const staged = await stageAccepted(page.request, "partial-refresh.txt");
    await page.route(
      `**/candidates/${encodeURIComponent(staged.candidateId)}/approve`,
      (route) =>
        route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            detail: {
              code: "partial_refresh",
              message: "Projection refresh failed.",
              recovery: {
                partial_approval_result: {
                  candidate_id: staged.candidateId,
                  candidate_revision: staged.revision + 1,
                  lesson_id: staged.lessonId,
                  relative_vault_path: staged.path,
                  vault_write_outcome: "created",
                  candidate_state_changed: true,
                  refresh_outcome: { refreshed: false },
                },
                canonical_lesson_persisted: true,
                candidate_approval_persisted: true,
                projection_refreshed: false,
              },
            },
          }),
        }),
    );

    await page.goto("/app/#/tritalele");
    await page
      .locator(".candidate-card")
      .filter({ hasText: "partial-refresh.txt" })
      .click();
    await page.getByRole("button", { name: "Approve to vault" }).click();
    await page.getByRole("button", { name: "Confirm approval" }).click();
    await expect(page.getByText(/partial_refresh/).first()).toBeVisible();
    await expect(page.getByText("Recovery details")).toBeVisible();
    await expect(page.getByLabel("Approval read-back")).toBeVisible();
  });

  test("semantic mode is advisory, preserves source evidence and shows non-blocking similarity warnings", async ({
    page,
  }) => {
    const semanticCandidate = {
      candidate_id: `sha256:${"c".repeat(64)}`,
      state: "staged",
      revision: 0,
      original_text:
        "Validate external data before it crosses an authority boundary.",
      proposed_text: "Validate external data before granting authority.",
      effective_text: "Validate external data before granting authority.",
      proposed_metadata: {
        topic: "architecture",
        source: "semantic-test",
        importance: 4,
        tags: ["validation", "authority"],
        date: "2026-09-18",
        title: "Validate before authority",
      },
      proposal_rationale:
        "The supplied passage explicitly requires validation before authority is granted.",
      approval_destination: {
        lesson_id: "architecture/2026-09-18.validate-before-authority",
        relative_vault_path:
          "architecture/2026-09-18.validate-before-authority.md",
      },
      provenance: {
        source_kind: "plain_text",
        source_logical_name: "semantic-source.txt",
        source_fingerprint: `sha256:${"d".repeat(64)}`,
        ingested_at: "2026-09-18T12:00:00+00:00",
        chunk_index: null,
        source_span: null,
        run_metadata: {
          strategy: "semantic",
          provider: "ollama",
          model: "test-model",
          locality: "local",
        },
        transformations: [],
        supporting_evidence: [
          {
            chunk_index: 0,
            source_span: { start: 0, end: 68 },
          },
        ],
        derivation_id: `sha256:${"e".repeat(64)}`,
      },
      review_history: [],
    };

    let semanticPreviewCalls = 0;
    let deterministicPreviewCalls = 0;

    await page.route("**/api/v1/tritalele/semantic/preview", async (route) => {
      semanticPreviewCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          preview: true,
          source: {
            kind: "plain_text",
            logical_name: "semantic-source.txt",
            fingerprint: `sha256:${"d".repeat(64)}`,
          },
          chunking: { max_characters: 2000 },
          candidate_ids: [semanticCandidate.candidate_id],
          created_candidate_ids: [],
          skipped_candidate_ids: [],
          pending_candidate_ids: [semanticCandidate.candidate_id],
          counts: { planned: 1, created: 0, skipped: 0, pending: 1 },
          candidates: [semanticCandidate],
        }),
      });
    });

    await page.route("**/api/v1/tritalele/ingestion/preview", async (route) => {
      deterministicPreviewCalls += 1;
      await route.abort();
    });

    await page.route("**/api/v1/tritalele/candidates", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1,
          candidates: [semanticCandidate],
        }),
      });
    });

    await page.route(
      `**/api/v1/tritalele/candidates/${encodeURIComponent(semanticCandidate.candidate_id)}`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(semanticCandidate),
        });
      },
    );

    await page.route("**/similar?explain=true", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query: semanticCandidate.effective_text,
          results: [
            {
              id: "architecture/existing",
              score: 0.88,
              text_preview: "Existing related validation lesson.",
              rank: 1,
              topic: "architecture",
              tags_shared: ["validation"],
            },
          ],
          meta: {
            data_mtime_ns: 1,
            model_mtime_ns: 1,
            top_k: 5,
            min_score: 0.1,
          },
        }),
      });
    });

    await page.goto("/app/#/tritalele");

    const ingestion = ingestionRegion(page);
    await ingestion.getByLabel("Extraction mode").selectOption("semantic");

    await expect(page.getByTestId("semantic-advisory")).toContainText(
      "never publish automatically",
    );

    await ingestion.getByLabel("Source name").fill("semantic-source.txt");
    await ingestion
      .getByLabel("Source text")
      .fill("Validate external data before it crosses an authority boundary.");

    await ingestion.getByRole("button", { name: "Create preview" }).click();

    await expect(page.getByTestId("ingestion-preview")).toBeVisible();
    expect(semanticPreviewCalls).toBe(1);
    expect(deterministicPreviewCalls).toBe(0);

    await page
      .locator(".candidate-card")
      .filter({ hasText: "semantic-source.txt" })
      .click();

    const review = page.getByTestId("semantic-review");
    await expect(review).toContainText("Semantic proposal review");
    await expect(review).toContainText(
      "Validate external data before it crosses an authority boundary.",
    );
    await expect(review).toContainText("Proposal rationale");
    await expect(review).toContainText("Derivation ID");
    await expect(review).toContainText("Chunk 0 · 0–68");
    await expect(review).toContainText("Related existing knowledge");
    await expect(review).toContainText("architecture/existing");
    await expect(review).toContainText("Similarity is a review warning only");
  });

  test("semantic similarity failure does not block candidate review", async ({
    page,
  }) => {
    const semanticCandidate = {
      candidate_id: `sha256:${"f".repeat(64)}`,
      state: "staged",
      revision: 0,
      original_text: "Keep authority decisions in deterministic code.",
      proposed_text: "Keep authority decisions deterministic.",
      effective_text: "Keep authority decisions deterministic.",
      proposed_metadata: null,
      proposal_rationale: "The source directly supports the proposal.",
      approval_destination: null,
      provenance: {
        source_kind: "plain_text",
        source_logical_name: "semantic-similarity-error.txt",
        source_fingerprint: `sha256:${"1".repeat(64)}`,
        ingested_at: "2026-09-18T12:00:00+00:00",
        chunk_index: null,
        source_span: null,
        run_metadata: { strategy: "semantic" },
        transformations: [],
        supporting_evidence: [
          { chunk_index: 0, source_span: { start: 0, end: 48 } },
        ],
        derivation_id: `sha256:${"2".repeat(64)}`,
      },
      review_history: [],
    };

    await page.route("**/api/v1/tritalele/candidates", (route) =>
      route.fulfill({
        json: { count: 1, candidates: [semanticCandidate] },
      }),
    );
    await page.route(
      `**/api/v1/tritalele/candidates/${encodeURIComponent(semanticCandidate.candidate_id)}`,
      (route) => route.fulfill({ json: semanticCandidate }),
    );
    await page.route("**/similar?explain=true", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          detail: { code: "model_unavailable", message: "unavailable" },
        }),
      }),
    );

    await page.goto("/app/#/tritalele");
    await page
      .locator(".candidate-card")
      .filter({ hasText: "semantic-similarity-error.txt" })
      .click();

    await expect(page.getByTestId("semantic-review")).toBeVisible();
    await expect(
      page.getByText(
        "Related-knowledge lookup is unavailable. Candidate review can continue.",
      ),
    ).toBeVisible();
    await expect(page.getByLabel("Proposed text")).toBeEnabled();
  });

  test("Italian semantic mode keeps advisory semantics", async ({ page }) => {
    await page.goto("/app/#/tritalele");
    await page.getByTestId("language-control").selectOption("it");

    const ingestion = page.getByRole("region", {
      name: "Raccogli nuove LeLe",
      exact: true,
    });

    await ingestion
      .getByLabel("Modalità di estrazione")
      .selectOption("semantic");

    await expect(page.getByTestId("semantic-advisory")).toContainText(
      "non vengono mai pubblicate automaticamente",
    );
    await expect(
      ingestion.getByRole("option", { name: "Semantica (consultiva)" }),
    ).toBeAttached();
  });
});
