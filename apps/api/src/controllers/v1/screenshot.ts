import { Request, Response } from "express";
import { logger } from "../../lib/logger";
import { authenticateUser } from "../auth";
import { RateLimiterMode } from "../../types";
import { scrapeURLWithEngine } from "../../scraper/scrapeURL/engines";
import { ScrapeOptions } from "../v1/types";
import { Meta } from "../../scraper/scrapeURL";

/**
 * Controller for getting a screenshot as base64 without storing it
 * @param req - The request object
 * @param res - The response object
 */
export async function getScreenshotAsBase64Controller(req: Request, res: Response) {
  try {
    const auth = await authenticateUser(req, res, RateLimiterMode.Scrape);
    if (!auth.success) {
      return res.status(auth.status).json({ error: auth.error });
    }

    const { url, fullPage, waitFor, timeout, headers, mobile } = req.body;

    if (!url) {
      return res.status(400).json({ 
        success: false, 
        error: "URL is required" 
      });
    }

    // Create a simple meta object with just what we need
    const meta = {
      id: `screenshot-base64-${auth.team_id}`,
      url,
      options: {
        formats: [fullPage ? "screenshot@fullPage" : "screenshot"] as ("markdown" | "html" | "rawHtml" | "content" | "links" | "screenshot" | "screenshot@fullPage" | "extract" | "json" | "compare")[],
        waitFor: waitFor || 0,
        timeout: timeout || 30000,
        headers: headers || undefined,
        mobile: mobile || false,
        onlyMainContent: false,
        parsePDF: true,
        skipTlsVerification: false,
        removeBase64Images: false,
        blockAds: true,
        fastMode: false,
        useMock: undefined
      } as ScrapeOptions,
      internalOptions: {
        teamId: auth.team_id
      },
      logger: logger.child({
        module: "ScreenshotBase64",
        scrapeId: `screenshot-base64-${auth.team_id}`,
        scrapeURL: url
      }),
      logs: [],
      featureFlags: new Set([fullPage ? "screenshot@fullScreen" : "screenshot"]),
      mock: null,
      pdfPrefetch: undefined
    };

    // Directly use the playwright engine to get a screenshot
    try {
      // Try with playwright first
      const result = await scrapeURLWithEngine(meta as Meta, "playwright", timeout || 30000);
      
      if (result && result.screenshot) {
        return res.status(200).json({
          success: true,
          data: {
            base64: result.screenshot
          }
        });
      }
    } catch (playwrightError) {
      logger.warn("Error using playwright for screenshot, trying fire-engine", { error: playwrightError });
      
      try {
        // Try with fire-engine as fallback
        const result = await scrapeURLWithEngine(meta as Meta, "fire-engine;playwright", timeout || 30000);
        
        if (result && result.screenshot) {
          return res.status(200).json({
            success: true,
            data: {
              base64: result.screenshot
            }
          });
        }
      } catch (fireEngineError) {
        logger.error("Error using fire-engine for screenshot", { error: fireEngineError });
      }
    }
    
    // If we reach here, all methods failed
    return res.status(500).json({
      success: false,
      error: "Failed to capture screenshot. All available methods failed."
    });
  } catch (error: any) {
    logger.error("Error in getScreenshotAsBase64Controller", { error });
    return res.status(500).json({
      success: false,
      error: error.message || "Internal server error"
    });
  }
}
