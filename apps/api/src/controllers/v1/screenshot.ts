import { Request, Response } from "express";
import { logger } from "../../lib/logger";
import { scrapeURL } from "../../scraper/scrapeURL";
import { ScrapeOptions } from "../v1/types";
import { authenticateUser } from "../auth";
import { RateLimiterMode } from "../../types";
import { Engine } from "../../scraper/scrapeURL/engines";

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

    // Use the existing scrapeURL function but intercept before storage
    const options: ScrapeOptions = {
      formats: [fullPage ? "screenshot@fullPage" : "screenshot"],
      waitFor: waitFor || 0,
      timeout: timeout || undefined,
      headers: headers || undefined,
      mobile: mobile || false,
      onlyMainContent: false,
      parsePDF: true,
      skipTlsVerification: false,
      removeBase64Images: false,
      blockAds: true,
      fastMode: false
    };
    
    // Determine which engines to use
    let forceEngine: Engine[] | undefined;
    
    // Check if we have fire-engine available
    if (process.env.FIRE_ENGINE_BETA_URL) {
      forceEngine = ["fire-engine;playwright" as Engine];
    } 
    // Check if we have playwright microservice available
    else if (process.env.PLAYWRIGHT_MICROSERVICE_URL) {
      forceEngine = ["playwright" as Engine];
    }
    // Check if we have ScrapingBee available
    else if (process.env.SCRAPING_BEE_API_KEY) {
      forceEngine = ["scrapingbee" as Engine];
    }

    const result = await scrapeURL(
      `screenshot-base64-${auth.team_id}`,
      url,
      options,
      {
        teamId: auth.team_id,
        // Skip the upload transformer
        skipTransformers: ["uploadScreenshot"],
        // Force specific engine that supports screenshots
        forceEngine: forceEngine
      }
    );

    if (result.success && result.document.screenshot) {
      // Return the base64 data directly
      return res.status(200).json({
        success: true,
        data: {
          base64: result.document.screenshot
        }
      });
    } else {
      return res.status(500).json({
        success: false,
        error: !result.success ? result.error.message || "Failed to capture screenshot" : "Failed to capture screenshot"
      });
    }
  } catch (error: any) {
    logger.error("Error in getScreenshotAsBase64Controller", { error });
    return res.status(500).json({
      success: false,
      error: error.message || "Internal server error"
    });
  }
}
