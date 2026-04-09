import { serve } from "https://deno.land/std@0.177.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const url = new URL(req.url);
  const action = url.searchParams.get("action");

  const apiKey = Deno.env.get("ALPACA_API_KEY");
  const secretKey = Deno.env.get("ALPACA_SECRET_KEY");

  if (!apiKey || !secretKey) {
    return new Response(JSON.stringify({ error: "Missing Alpaca credentials in environment." }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const alpacaHeaders = {
    "APCA-API-KEY-ID": apiKey,
    "APCA-API-SECRET-KEY": secretKey,
    "Accept": "application/json",
  };

  try {
    if (action === "assets") {
      // Fetch assets
      const response = await fetch("https://paper-api.alpaca.markets/v2/assets?status=active", {
        headers: alpacaHeaders,
      });

      if (!response.ok) {
        throw new Error(`Alpaca API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      // Filter for active us_equity and crypto
      const filtered = data.filter((asset: any) =>
        asset.status === "active" &&
        (asset.class === "us_equity" || asset.class === "crypto")
      );

      return new Response(JSON.stringify(filtered), {
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json",
          "Cache-Control": "public, s-maxage=3600",
        },
      });
    } else if (action === "bars") {
      const symbol = url.searchParams.get("symbol");
      const timeframe = url.searchParams.get("timeframe");
      const start = url.searchParams.get("start");
      const end = url.searchParams.get("end");
      const assetClass = url.searchParams.get("asset_class");

      if (!symbol || !timeframe || !start) {
        return new Response(JSON.stringify({ error: "Missing required parameters for bars: symbol, timeframe, start" }), {
          status: 400,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }

      let fetchUrl = "";
      if (assetClass === "crypto") {
        fetchUrl = `https://data.alpaca.markets/v1beta3/crypto/us/bars?symbols=${encodeURIComponent(symbol)}&timeframe=${timeframe}&start=${start}`;
        if (end) fetchUrl += `&end=${end}`;
      } else {
        // us_equity
        fetchUrl = `https://data.alpaca.markets/v2/stocks/bars?symbols=${encodeURIComponent(symbol)}&timeframe=${timeframe}&start=${start}&adjustment=all`;
        if (end) fetchUrl += `&end=${end}`;
      }

      const response = await fetch(fetchUrl, {
        headers: alpacaHeaders,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Alpaca API error: ${response.status} ${response.statusText} - ${errText}`);
      }

      const data = await response.json();

      return new Response(JSON.stringify(data), {
        headers: {
          ...corsHeaders,
          "Content-Type": "application/json",
          "Cache-Control": "public, s-maxage=3600",
        },
      });
    } else {
      return new Response(JSON.stringify({ error: "Invalid action. Use 'assets' or 'bars'." }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
