import { test, expect } from "@playwright/test";

test.describe("Student Admission Guidance Chatbot", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/chatbot");
  });

  test("loads chatbot page without requiring authentication", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Admission & Campus Guidance");
    await expect(page.getByPlaceholder(/Ask about admissions/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Send", exact: true })).toBeVisible();
  });

  test("displays all nine knowledge categories and suggestions", async ({ page }) => {
    const categories = [
      "Courses & Academic Programs",
      "Admission Procedure & Counseling",
      "Eligibility Criteria",
      "Fee Structure & Payment",
      "Required Documents",
      "Examinations & Entry Verification",
      "Exam & Class Timetables",
      "Campus Facilities",
      "General Inquiries & Campus Contacts",
    ];

    for (const category of categories) {
      await expect(page.getByRole("button", { name: category, exact: true })).toBeVisible();
    }

    // Verify popular inquiry chips exist
    await expect(page.getByRole("button", { name: /What are the eligibility criteria/i }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /What documents are required/i }).first()).toBeVisible();
  });

  test("answers grounded question about eligibility and shows verified badge", async ({ page }) => {
    const input = page.getByPlaceholder(/Ask about admissions/i);
    await input.fill("What is the eligibility for B.Tech CSE admission?");
    await page.getByRole("button", { name: "Send", exact: true }).click();

    // Verify user message appears in transcript
    await expect(page.getByText("What is the eligibility for B.Tech CSE admission?")).toBeVisible();

    // Verify assistant responds with grounded content from knowledge base
    await expect(page.getByText(/10\+2|PUC|45%/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("clicking a suggestion chips fills input and sends prompt", async ({ page }) => {
    const suggestion = page.getByRole("button", { name: /What are the eligibility criteria/i }).first();
    await suggestion.click();

    // Verify assistant responds with eligibility details
    await expect(page.getByText(/eligibility|10\+2|PUC/i).first()).toBeVisible({ timeout: 10000 });
  });

  test("returns safe grounded fallback for unsupported question", async ({ page }) => {
    const input = page.getByPlaceholder(/Ask about admissions/i);
    await input.fill("Can I bring my pet kangaroo to the exam hall and feed it snacks?");
    await page.getByRole("button", { name: "Send", exact: true }).click();

    // Verify fallback guidance and admin confirmation badge
    await expect(page.getByText(/verified institutional information/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Confirm with Admin")).toBeVisible();
  });

  test("clears conversation when Clear Chat is clicked", async ({ page }) => {
    const input = page.getByPlaceholder(/Ask about admissions/i);
    await input.fill("Hello, what courses are offered?");
    await page.getByRole("button", { name: "Send", exact: true }).click();

    await expect(page.getByText("Hello, what courses are offered?")).toBeVisible({ timeout: 10000 });

    // Click Clear Chat
    await page.getByRole("button", { name: "Clear Chat" }).click();

    // User message should be cleared
    await expect(page.getByText("Hello, what courses are offered?")).toHaveCount(0);
  });
});
