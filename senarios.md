## 1. Landing — Navigation — Entry Points

### Scenario 1: Navigation & CTAs

- Click header buttons (Login / Signup / Pricing)
- Click footer links
- Click all CTAs

**Expected:**
- All links work correctly
- No broken links

### Scenario 2: Banner Behavior

- Open landing (logged-out)
- Login and revisit
- Click banner CTAs

**Expected:**
- Banner changes based on user state
- CTA redirects correctly

---

## 2. Authentication Flow

### Scenario 3: Signup & Login

- Signup with email + OTP (valid / invalid / expired)
- Login with valid / invalid credentials
- Login via Google / Apple
- Signup via Google / Apple

**Expected:**
- Valid flows succeed
- Invalid inputs show error

### Scenario 4: Forgot Password

- Request reset (valid / invalid email)
- Enter valid / invalid / expired OTP
- Reset password
- Login with old password

**Expected:**
- Reset works only with valid data
- Old password no longer works

### Scenario 5: Notifications

- Complete Signup / Login / Reset

**Expected:**
- Events logged in Slack
- Welcome email sent

---

## 3. Pricing — Plan — Access Control

### Scenario 6: Pricing Flow

- Click plan (logged-out / logged-in)
- Click Upgrade / Downgrade / Buy credits

**Expected:**
- Correct auth / checkout flow
- Correct plan action flow

---

## 4. Dashboard — Upload

### Scenario 7: Upload Validation

- Upload valid image
- Upload 50 MB file
- Upload unsupported format
- Upload invalid dimensions
- Upload corrupted file

**Expected:**
- Valid upload succeeds
- Invalid cases show error

---

## 5. Generate Preconditions

### Scenario 8: Generate Validation

- Click Generate without upload
- Upload image
- Skip required fields (Space / Style)
- Click Generate

**Expected:**
- Proper errors shown

---

## 6. Core Generation (All Services)

### Scenario 9: Services Generation

- Generate image in all 11 services
- Test services with required widgets (Space / Style)

**Expected:**
- Generation works for all services
- Required fields enforced

---

## 7. Virtual Staging (VS Focus)

### Scenario 10: VS Variations

- Generate with different styles (Modern / Hampton / etc.)
- Generate without style (Prime)
- Generate with Remove Furniture ON
- Generate with Remove Furniture OFF

**Expected:**
- Style applied correctly
- Toggle affects output

---

## Multi-Angle Feature

### Scenario 11: Enable Multi-Angle Flow

- Upload base image
- Enable Multi-Angle toggle
- Upload second angle image

**Expected:**
- Second uploader appears
- Second image uploaded successfully

### Scenario 12: Multi-Angle Second Image Validation

- Upload invalid second image (large / wrong format / invalid dimension)

**Expected:**
- Error shown
- Upload blocked

### Scenario 13: Multi-Angle Generate

- Upload both images
- Select required fields
- Click Generate

**Expected:**
- Generation completes using both images

### Scenario 14: Toggle Multi-Angle OFF After Upload

- Upload both images
- Disable Multi-Angle

**Expected:**
- Second image removed or ignored

### Scenario 15: Upload Sources (Logged-in User)

- Upload second image from:
  - Computer
  - Studio

**Expected:**
- Both upload methods work

### Scenario 16: Upload Sources (Logged-out User)

- Enable Multi-Angle
- Try uploading second image

**Expected:**
- Only computer upload available

### Scenario 17: Generate With Only One Image (Multi-Angle ON)

- Upload first image
- Enable Multi-Angle
- Do not upload second image
- Click Generate

**Expected:**
- Error shown

---

## 8. Post-Generation Actions

### Scenario 18: Actions

- Fullscreen
- Compare
- Feedback
- Bookmark

**Expected:**
- All actions work correctly

---

## 9. Download Flow

### Scenario 19: Download Variations

- Download normal image
- Download upscale
- Download with logo
- Download with VS label
- Download with Remove Furniture ON / OFF

**Expected:**
- Correct file downloaded
- Options applied correctly

### Scenario 20: File Validation

- Open downloaded files

**Expected:**
- Files are correct and usable

---

## 10. VS — Remove Item

### Scenario 21: Remove Item

- Remove object from image
- Download result

**Expected:**
- Object removed correctly
- Download matches result

---

## 11. User Types & Credit Behavior

### Scenario 22: Free User

- Generate image
- Download image
- Use all credits, then generate again

**Expected:**
- Watermark visible
- Upgrade shown
- Not enough credit modal

### Scenario 23: Restricted User

- Click Generate / Regenerate

**Expected:**
- Blocked + no active plan modal

### Scenario 24: Paid User (Credit = 0)

- Generate new image
- Regenerate image

**Expected:**
- Generate: Buy/Upgrade modal
- Regenerate works

### Scenario 25: Paid User (With Credit)

- Generate image
- Regenerate image

**Expected:**
- Works normally

### Scenario 26: Credit Logic

- Generate in different services
- Regenerate

**Expected:**
- Generate: 1 credit deducted
- Regenerate: no credit deducted
