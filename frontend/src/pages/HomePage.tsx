import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function HomePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">BoardInsight</h1>
      <Card>
        <CardHeader>
          <CardTitle>Bem-vindo</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-slate-600">
          Portal interno de leitura e análise de boards Businessmap.
        </CardContent>
      </Card>
    </div>
  );
}
