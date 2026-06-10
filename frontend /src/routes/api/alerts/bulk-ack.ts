import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/api/alerts/bulk-ack")({
  server: {
    handlers: {
      PATCH: async ({ request }) => {
        const body = await request.json();
        const { ids } = body as { ids?: string[] };

        if (!Array.isArray(ids) || ids.length === 0) {
          return new Response(
            JSON.stringify({ error: "Missing or invalid ids" }),
            { status: 400, headers: { "Content-Type": "application/json" } }
          );
        }

        // In a real app this would update the database.
        // For now we return success so the UI can update its local state.
        return new Response(
          JSON.stringify({ success: true, acknowledged: ids.length }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      },
    },
  },
});
