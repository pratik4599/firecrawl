import { Request, Response } from "express";
import { logger } from "../../lib/logger";
import { authenticateUser } from "../auth";
import { RateLimiterMode } from "../../types";
import axios from "axios";
import * as puppeteer from "puppeteer";

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

    // Try to take a screenshot using Playwright service if available
    if (process.env.PLAYWRIGHT_MICROSERVICE_URL) {
      try {
        logger.info(`Taking screenshot of ${url} using Playwright microservice`);
        
        // Launch a browser directly
        const browser = await puppeteer.launch({
          headless: true,
          args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
        
        try {
          const page = await browser.newPage();
          
          // Set mobile viewport if requested
          if (mobile) {
            await page.setViewport({
              width: 375,
              height: 667,
              isMobile: true,
              hasTouch: true
            });
          }
          
          // Set custom headers if provided
          if (headers && Object.keys(headers).length > 0) {
            await page.setExtraHTTPHeaders(headers);
          }
          
          // Navigate to the URL
          await page.goto(url, {
            waitUntil: 'networkidle0',
            timeout: timeout || 30000
          });
          
          // Wait additional time if specified
          if (waitFor && waitFor > 0) {
            await new Promise(resolve => setTimeout(resolve, waitFor));
          }
          
          // Take screenshot
          const screenshotBuffer = await page.screenshot({ 
            fullPage: fullPage || false,
            type: 'png',
            encoding: 'binary'
          });
          
          // Convert to base64
          const base64Data = `data:image/png;base64,${screenshotBuffer.toString('base64')}`;
          
          await browser.close();
          
          return res.status(200).json({
            success: true,
            data: {
              base64: base64Data
            }
          });
        } catch (err) {
          await browser.close();
          throw err;
        }
      } catch (playwrightError) {
        logger.error("Error using Playwright for screenshot", { error: playwrightError });
        // Fall through to try other methods
      }
    }
    
    // If we reach here, try using axios to call a remote service
    try {
      // Try using Fire Engine if available
      if (process.env.FIRE_ENGINE_BETA_URL) {
        logger.info(`Taking screenshot of ${url} using Fire Engine`);
        
        const fireEngineResponse = await axios.post(
          `${process.env.FIRE_ENGINE_BETA_URL}/screenshot`, 
          {
            url,
            fullPage: fullPage || false,
            waitFor: waitFor || 0,
            timeout: timeout || 30000,
            headers: headers || {},
            mobile: mobile || false
          },
          { timeout: (timeout || 30000) + 5000 }
        );
        
        if (fireEngineResponse.data && fireEngineResponse.data.screenshot) {
          return res.status(200).json({
            success: true,
            data: {
              base64: fireEngineResponse.data.screenshot
            }
          });
        }
      }
    } catch (axiosError) {
      logger.error("Error using Fire Engine for screenshot", { error: axiosError });
      // Fall through to the error response
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
