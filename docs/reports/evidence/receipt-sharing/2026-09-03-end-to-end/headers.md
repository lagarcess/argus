# Response headers

## GET /r/{public_id} (server-rendered page)
HTTP/1.1 200 OK
Cache-Control: no-cache, must-revalidate

## GET /r/{public_id}/opengraph-image
HTTP/1.1 200 OK
cache-control: no-store, max-age=0
content-type: image/png
x-robots-tag: noindex, nofollow, noimageindex

## GET api /public/receipts/{public_id} after owner revoke and after chat deletion: status revoked, payload null (see e-owner-list-after-delete)
