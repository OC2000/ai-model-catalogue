using System.Text.Json;
using System.Text.RegularExpressions;
namespace AIConnect.Core;

/// <summary>Shared, offline production feed envelope checks. Does not establish provenance.</summary>
public sealed record CsvFeedContract(string ReleaseId,string Sha256,long SizeBytes,Uri CsvUrl) {
    public const int MaximumManifestBytes=16384;
    public static CsvFeedContract Parse(byte[] bytes,DateTimeOffset now) {
        if(bytes.Length>MaximumManifestBytes)throw new InvalidDataException("Manifest exceeds 16384 bytes.");
        using var json=JsonDocument.Parse(bytes);
        var root=json.RootElement;
        if(root.GetProperty("schemaVersion").GetInt32()!=6)throw new InvalidDataException("Manifest schemaVersion must be 6.");
        var release=root.GetProperty("releaseId").GetString();
        var hash=root.GetProperty("sha256").GetString() ?? "";
        var size=root.GetProperty("sizeBytes").GetInt64();
        if(string.IsNullOrWhiteSpace(release) || release.Length>160 || size<=0 || size>CsvCatalogueSchema.MaximumBytes || !Regex.IsMatch(hash,"\\A[0-9a-fA-F]{64}\\z"))throw new InvalidDataException("Invalid releaseId, sizeBytes or sha256.");
        if(!root.GetProperty("publishedUtc").TryGetDateTimeOffset(out var date) || date>now.AddMinutes(5))throw new InvalidDataException("Invalid or future publishedUtc.");
        var uri=new Uri(root.GetProperty("csvUrl").GetString()!,UriKind.Absolute);
        if(uri.Scheme!="https" || uri.Host!="raw.githubusercontent.com" || !uri.IsDefaultPort || uri.UserInfo!="" || uri.Query!="" || uri.Fragment!="" ||
            !Regex.IsMatch(uri.AbsolutePath,"\\A/OC2000/ai-model-catalogue/[0-9a-fA-F]{40}/releases/[A-Za-z0-9._-]+\\.csv\\z"))throw new InvalidDataException("CSV URL must pin an exact commit in the production repository releases directory.");
        return new(release,hash,size,uri);
    }
}
