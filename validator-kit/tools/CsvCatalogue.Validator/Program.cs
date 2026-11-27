using System.Text.Json;
using CsvCatalogue.Validator;

return Cli.Run(args);

public static class Cli {
    public static int Run(string[] args) {
        try {
            var options=new Dictionary<string,string>(StringComparer.Ordinal);
            for(int i=0;i<args.Length;i+=2) {
                if(i+1>=args.Length || !new[]{"--csv","--previous","--manifest","--kind","--json"}.Contains(args[i]) || !options.TryAdd(args[i],args[i+1]))throw new ArgumentException("Invalid or duplicate option.");
            }
            if(!options.ContainsKey("--csv") || !options.TryGetValue("--kind",out var kind) || kind is not ("candidate" or "synthetic"))throw new ArgumentException("Use --csv FILE --kind candidate|synthetic [--previous FILE] [--manifest FILE] [--json FILE].");
            if(options.TryGetValue("--json",out var output) && new[]{"--csv","--previous","--manifest"}.Where(options.ContainsKey).Any(k=>Path.GetFullPath(options[k]).Equals(Path.GetFullPath(output),StringComparison.OrdinalIgnoreCase)))throw new ArgumentException("Report cannot overwrite an input.");
            var report=Validation.Run(options["--csv"],kind,options.GetValueOrDefault("--previous"),options.GetValueOrDefault("--manifest"));
            var json=JsonSerializer.Serialize(report,new JsonSerializerOptions{WriteIndented=true});
            if(output is not null) { using var file=new FileStream(output,FileMode.CreateNew,FileAccess.Write);using var writer=new StreamWriter(file);writer.Write(json); }
            Console.Out.WriteLine(json);
            Console.Error.WriteLine($"{(report.Valid?"VALID":"REJECTED")} schema 6; {report.Bytes} bytes; {report.Sha256}; {report.Diagnostics.Count} diagnostics. Not publication approval.");
            return report.Valid?0:1;
        } catch(Exception e) {
            Console.Out.WriteLine(JsonSerializer.Serialize(new {Valid=false,PublicationApproved=false,ExitCode=2,Diagnostics=new[]{new Diagnostic("error","TOOL_FAILURE","invocation:$",e.Message)}}));
            Console.Error.WriteLine("TOOL_FAILURE: "+e.Message);return 2;
        }
    }
}
