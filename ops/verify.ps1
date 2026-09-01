try {
  $r = Invoke-WebRequest -Uri 'https://sct5dzd.xyz/' -UseBasicParsing -TimeoutSec 20
  'HTTP ' + $r.StatusCode + ' len=' + $r.Content.Length
} catch {
  'ERR: ' + $_.Exception.Message
}
