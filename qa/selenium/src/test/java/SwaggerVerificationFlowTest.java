import org.openqa.selenium.By;
import org.openqa.selenium.JavascriptExecutor;
import org.openqa.selenium.OutputType;
import org.openqa.selenium.TakesScreenshot;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.chrome.ChromeDriver;
import org.openqa.selenium.json.Json;
import org.openqa.selenium.support.ui.WebDriverWait;

import org.testng.Assert;
import org.testng.Reporter;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.testng.ITestResult;


public class SwaggerVerificationFlowTest {

    private WebDriver driver;
    private WebDriverWait wait;

    private String accountType;
    private String testEmail;
    private String password;
    private String token;

    private String lastStatus;
    private String lastBody;
    private String lastRequestBody;
    private WebElement lastOperation;

    private String adminEmail;
    private String adminPassword;
    private String adminToken;
    private String uploadType;
    private Path uploadFile;

    private final Json json = new Json();

    private static final String RUN_ID =
            LocalDateTime.now().format(
                    DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")
            )
                    + "_"
                    + UUID.randomUUID().toString().substring(0, 8);

    private static final Path EVIDENCE_ROOT = Path.of(
            "target",
            "test-evidence",
            "verification_" + RUN_ID
    );

    @BeforeMethod
    public void setup() throws Exception {
        Path config = Path.of(System.getProperty("qa.admin.file", "qa-admin.json"));
        if (!Files.isRegularFile(config)) {
            throw new IllegalStateException("Missing qa-admin.json. Run prepare_meal215_qa.py first.");
        }
        Map<?, ?> admin = json.toType(Files.readString(config), Map.class);
        adminEmail = (String) admin.get("email");
        adminPassword = (String) admin.get("password");
        if (adminEmail == null || adminPassword == null) {
            throw new IllegalStateException("Invalid QA admin configuration");
        }
        adminToken = null;
        uploadType = null;
        uploadFile = null;
        accountType = null;
        testEmail = null;
        token = null;
        lastStatus = null;
        lastBody = null;
        lastOperation = null;

        password = "QaTest-" + UUID.randomUUID() + "!";

        driver = new ChromeDriver();
        driver.manage().window().maximize();

        wait = new WebDriverWait(
                driver,
                Duration.ofSeconds(25)
        );
    }

    private void openSwagger() {
        lastOperation = null;
        lastStatus = null;
        lastBody = null;

        String swaggerUrl = System.getProperty("swagger.url", "http://127.0.0.1:8001/docs");
        java.net.URI uri = java.net.URI.create(swaggerUrl);
        if (!List.of("127.0.0.1", "localhost").contains(uri.getHost())) {
            throw new IllegalArgumentException("This QA suite only supports a local test backend");
        }
        driver.get(swaggerUrl);

        wait.until(d ->
                !d.findElements(
                        By.cssSelector(".opblock")
                ).isEmpty()
        );
    }

    private void scrollTo(WebElement element) {
        ((JavascriptExecutor) driver).executeScript(
                "arguments[0].scrollIntoView({block:'center'});",
                element
        );
    }

    private WebElement findOperation(String method, String path) {
        return wait.until(d -> {
            for (WebElement operation : d.findElements(
                    By.cssSelector(".opblock")
            )) {
                List<WebElement> methods = operation.findElements(
                        By.cssSelector(".opblock-summary-method")
                );

                List<WebElement> paths = operation.findElements(
                        By.cssSelector(".opblock-summary-path")
                );

                if (!methods.isEmpty() && !paths.isEmpty()
                        && methods.get(0).getText().trim().equals(method)
                        && paths.get(0).getText().trim().equals(path)) {
                    return operation;
                }
            }

            return null;
        });
    }

    private WebElement visible(
            WebElement parent,
            String selector
    ) {
        return wait.until(d -> {
            for (WebElement element : parent.findElements(
                    By.cssSelector(selector)
            )) {
                if (element.isDisplayed() && element.isEnabled()) {
                    return element;
                }
            }

            return null;
        });
    }

    private WebElement currentDialog() {
        return wait.until(org.openqa.selenium.support.ui.ExpectedConditions
                .visibilityOfElementLocated(By.cssSelector(".dialog-ux")));
    }

    private void authorize(String accessToken) {
        WebElement topButton = wait.until(
                org.openqa.selenium.support.ui.ExpectedConditions.elementToBeClickable(
                        By.cssSelector(".auth-wrapper button.authorize")));
        scrollTo(topButton);
        topButton.click();
        currentDialog();

        // Reacquire elements after React updates the authorization dialog.
        for (WebElement button : currentDialog().findElements(By.tagName("button"))) {
            if (button.isDisplayed() && button.getText().trim().equalsIgnoreCase("Logout")) {
                button.click();
                break;
            }
        }

        WebElement input = wait.until(d -> {
            try {
                for (WebElement field : d.findElements(By.cssSelector(".dialog-ux input"))) {
                    if (field.isDisplayed() && field.isEnabled()) return field;
                }
            } catch (org.openqa.selenium.StaleElementReferenceException ignored) {
                return null;
            }
            return null;
        });
        input.click();
        input.sendKeys(org.openqa.selenium.Keys.chord(org.openqa.selenium.Keys.CONTROL, "a"));
        input.sendKeys(org.openqa.selenium.Keys.BACK_SPACE);
        input.sendKeys(accessToken);
        wait.until(d -> accessToken.equals(input.getDomProperty("value")));

        WebElement authorizeButton = wait.until(d -> {
            try {
                for (WebElement button : d.findElements(By.cssSelector(".dialog-ux button.authorize"))) {
                    if (button.isDisplayed() && button.isEnabled()
                            && button.getText().trim().equalsIgnoreCase("Authorize")) return button;
                }
            } catch (org.openqa.selenium.StaleElementReferenceException ignored) {
                return null;
            }
            return null;
        });
        authorizeButton.click();
        wait.until(d -> {
            try {
                return d.findElements(By.cssSelector(".dialog-ux button"))
                        .stream().anyMatch(b -> b.isDisplayed()
                                && b.getText().trim().equalsIgnoreCase("Logout"));
            } catch (org.openqa.selenium.StaleElementReferenceException ignored) {
                return false;
            }
        });
        wait.until(org.openqa.selenium.support.ui.ExpectedConditions.elementToBeClickable(
                By.cssSelector(".dialog-ux button.btn-done"))).click();
        wait.until(org.openqa.selenium.support.ui.ExpectedConditions
                .invisibilityOfElementLocated(By.cssSelector(".dialog-ux")));
    }

    private void execute(
            String method,
            String path,
            String requestBody,
            String accessToken
    ) {
        execute(method, path, requestBody, accessToken, Map.of());
    }

    private void execute(String method, String path, String requestBody,
                         String accessToken, Map<String, String> parameters) {
        // Reload between requests so an old response cannot be
        // mistaken for the result of a new request.
        openSwagger();
        lastRequestBody = requestBody;

        if (accessToken != null) {
            authorize(accessToken);
        }

        lastOperation = findOperation(method, path);

        if (!lastOperation.getAttribute("class").contains("is-open")) {
            WebElement summary = lastOperation.findElement(
                    By.cssSelector(".opblock-summary")
            );

            scrollTo(summary);
            summary.click();
        }

        WebElement tryButton = visible(
                lastOperation,
                ".try-out__btn"
        );

        scrollTo(tryButton);
        tryButton.click();

        for (Map.Entry<String, String> entry : parameters.entrySet()) {
            WebElement field = visible(lastOperation,
                    "tr[data-param-name='" + entry.getKey() + "'][data-param-in='path'] input");
            field.clear();
            field.sendKeys(entry.getValue());
        }

        if (uploadFile != null) {
            WebElement row = wait.until(d -> {
                List<WebElement> rows = lastOperation.findElements(By.xpath(
                        ".//tr[@data-param-name='document_type' or @data-property-name='document_type' or td[contains(.,'document_type')]]"));
                return rows.isEmpty() ? null : rows.get(0);
            });
            List<WebElement> selects = row.findElements(By.tagName("select"));
            if (!selects.isEmpty()) {
                new org.openqa.selenium.support.ui.Select(selects.get(0))
                        .selectByValue(uploadType);
            } else {
                WebElement field = visible(row, "input,textarea");
                field.clear();
                field.sendKeys(uploadType);
            }
            lastOperation.findElement(By.cssSelector("input[type='file']"))
                    .sendKeys(uploadFile.toAbsolutePath().toString());
        }

        if (requestBody != null) {
            WebElement textarea = visible(
                    lastOperation,
                    "textarea.body-param__text"
            );

            // Validate locally; do not send malformed test JSON to the API.
            json.toType(requestBody, Map.class);
            scrollTo(textarea);
            textarea.click();
            textarea.sendKeys(org.openqa.selenium.Keys.chord(
                    org.openqa.selenium.Keys.CONTROL, "a"));
            textarea.sendKeys(org.openqa.selenium.Keys.BACK_SPACE);
            textarea.sendKeys(requestBody);
            textarea.sendKeys(org.openqa.selenium.Keys.TAB);
            wait.until(d -> requestBody.equals(textarea.getDomProperty("value")));
        }

        WebElement executeButton = visible(
                lastOperation,
                "button.execute"
        );

        scrollTo(executeButton);
        executeButton.click();

        lastStatus = wait.until(d -> {
            for (WebElement element : lastOperation.findElements(
                    By.cssSelector(
                            ".live-responses-table .response-col_status"
                    )
            )) {
                String text = element.getText().trim();

                if (text.matches("(?s)^\\d{3}.*")) {
                    return text.substring(0, 3);
                }
            }

            return null;
        });

        lastBody = wait.until(d -> {
            for (WebElement element : lastOperation.findElements(
                    By.cssSelector(".live-responses-table pre")
            )) {
                String text = element.getText().trim();

                if (!text.isEmpty()) {
                    return text;
                }
            }

            return null;
        });
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> responseObject() {
        return json.toType(lastBody, Map.class);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> nested(
            Map<String, Object> object,
            String key
    ) {
        Assert.assertTrue(
                object.get(key) instanceof Map,
                "Missing object: " + key
        );

        return (Map<String, Object>) object.get(key);
    }

    private void assertNoPassword() {
        Assert.assertFalse(
                lastBody.contains(password),
                "Response exposed the submitted password"
        );

        Assert.assertFalse(
                lastBody.contains("\"password_hash\""),
                "Response exposed a password hash"
        );
    }

    private void assertError(String expectedCode) {
        Map<String, Object> error = nested(
                responseObject(),
                "error"
        );

        Assert.assertEquals(error.get("code"), expectedCode);
        Assert.assertTrue(error.get("message") instanceof String);
        Assert.assertFalse(
                ((String) error.get("message")).isBlank()
        );
        Assert.assertTrue(error.get("fields") instanceof List);
        Assert.assertTrue(((List<?>) error.get("fields")).isEmpty());
        assertNoPassword();
    }

    private String redact(String text) {
        if (text == null) {
            return "";
        }

        String redacted = text.replace(
                password,
                "[REDACTED_PASSWORD]"
        );

        if (token != null && !token.isBlank()) {
            redacted = redacted.replace(
                    token,
                    "[REDACTED_TOKEN]"
            );
        }

        // Also handles a token returned before it was assigned
        // to the Java token variable.
        if (adminPassword != null) redacted = redacted.replace(adminPassword, "[REDACTED_PASSWORD]");
        if (adminToken != null) redacted = redacted.replace(adminToken, "[REDACTED_TOKEN]");
        return redacted.replaceAll("[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}\\.[A-Za-z0-9_-]{10,}", "[REDACTED_TOKEN]").replaceAll(
                "(\"access_token\"\\s*:\\s*\")[^\"]*(\")",
                "$1[REDACTED_TOKEN]$2"
        );
    }

    private void saveEvidence(String step, String result)
            throws Exception {

        Path directory = EVIDENCE_ROOT.resolve(result);
        Files.createDirectories(directory);

        String safeName = (
                accountType + "_" + step
        ).replaceAll("[^a-zA-Z0-9_-]", "_");

        String timestamp = LocalDateTime.now().format(
                DateTimeFormatter.ofPattern("HHmmss_SSS")
        );

        String filename = safeName + "_" + timestamp;

        byte[] image;

        List<WebElement> tables = driver.findElements(
                By.cssSelector(
                        ".opblock.is-open .live-responses-table"
                )
        );

        if (!tables.isEmpty()) {
            WebElement table = tables.get(0);

            // Redact the rendered evidence only, after assertions.
            // This does not modify the API request or response.
            for (WebElement block : table.findElements(
                    By.cssSelector("pre")
            )) {
                ((JavascriptExecutor) driver).executeScript(
                        "arguments[0].textContent = arguments[1];",
                        block,
                        redact(block.getText())
                );
            }

            scrollTo(table);
            image = table.getScreenshotAs(OutputType.BYTES);

        } else {
            // Do not capture a credential-filled page on a UI failure.
            // Mask form fields and hide request/authentication sections.
            ((JavascriptExecutor) driver).executeScript("""
                document.querySelectorAll('input,textarea')
                  .forEach(e => { e.value = '[REDACTED]'; });

                document.querySelectorAll(
                  '.curl-command,.request-snippets,.auth-container'
                ).forEach(e => { e.style.visibility = 'hidden'; });

                document.querySelectorAll('pre').forEach(
                  e => { e.textContent = '[REDACTED DIAGNOSTIC CONTENT]'; }
                );
                """);

            image = ((TakesScreenshot) driver).getScreenshotAs(
                    OutputType.BYTES
            );
        }

        Path screenshot = directory.resolve(filename + ".png");
        Files.write(screenshot, image);

        String summary =
                "Scenario: " + accountType + " / " + step + "\n"
                        + "Result: " + result + "\n"
                        + "Time: " + LocalDateTime.now() + "\n"
                        + "QA account: " + testEmail + "\n"
                        + "HTTP status: " + lastStatus + "\n"
                        + "Request body:\n" + redact(lastRequestBody) + "\n"
                        + "Response:\n" + redact(lastBody) + "\n";

        Files.writeString(
                directory.resolve(filename + ".txt"),
                summary,
                StandardCharsets.UTF_8
        );

        Reporter.log(
                result + ": " + accountType + " / " + step,
                true
        );

        Reporter.log(
                "Screenshot: " + screenshot.toAbsolutePath(),
                true
        );
    }

    private void verifyStep(String step, Runnable assertions)
            throws Exception {

        try {
            assertions.run();
        } catch (AssertionError | RuntimeException failure) {
            try {
                saveEvidence(step, "FAIL");
            } catch (Exception evidenceError) {
                failure.addSuppressed(evidenceError);
            }

            throw failure;
        }

        saveEvidence(step, "PASS");
    }

    private long id(Map<String, Object> data, String key) {
        Assert.assertTrue(data.get(key) instanceof Number, "Missing numeric " + key);
        return ((Number) data.get(key)).longValue();
    }

    private Map<String, String> params(long application) {
        return Map.of("application_id", Long.toString(application));
    }

    private String appPath(String suffix) {
        return "/api/v1/organization-applications/{application_id}" + suffix;
    }

    private String adminPath(String suffix) {
        return "/api/v1/admin/organization-applications/{application_id}" + suffix;
    }

    private void error(int status, String code) {
        Assert.assertEquals(lastStatus, Integer.toString(status));
        Map<String, Object> e = nested(responseObject(), "error");
        Assert.assertEquals(e.get("code"), code);
        Assert.assertTrue(e.get("message") instanceof String);
        Assert.assertFalse(((String) e.get("message")).isBlank());
        Assert.assertTrue(e.get("fields") instanceof List);
        assertNoPassword();
    }

    private void success() {
        Assert.assertEquals(lastStatus, "200");
        assertNoPassword();
    }

    private String login(String email, String pwd) {
        execute("POST", "/api/v1/auth/login",
                json.toJson(Map.of("email", email, "password", pwd)), null);
        Assert.assertEquals(lastStatus, "200", "Login failed; check QA admin and backend signing configuration");
        Map<String, Object> data = nested(responseObject(), "data");
        Assert.assertEquals(data.get("token_type"), "bearer");
        Assert.assertTrue(data.get("access_token") instanceof String);
        String result = (String) data.get("access_token");
        Assert.assertFalse(result.isBlank());
        return result;
    }

    private String organization() {
        Map<String, Object> p = new java.util.LinkedHashMap<>();
        p.put("organization_type", accountType);
        p.put("name", "MEAL215 verification " + accountType);
        p.put("registration_number", "QA215-" + UUID.randomUUID());
        p.put("contact_email", testEmail);
        p.put("address_line", "123 QA Test Road");
        p.put("city", "Kurunegala");
        p.put("representative_name", "Selenium QA");
        if (accountType.equals("business")) {
            p.put("business_subtype", "restaurant");
            p.put("pickup_location", "123 QA Test Road, Kurunegala");
        } else {
            p.put("registration_authority", "QA Test Authority");
            p.put("registration_date", "2020-01-01");
            p.put("operational_details", Map.of("operational_capability", "Food distribution"));
        }
        return json.toJson(p);
    }

    @SuppressWarnings("unchecked")
    private void ownStatus(long application, String status, String note) {
        success();
        Object rows = responseObject().get("data");
        Assert.assertTrue(rows instanceof List);
        Assert.assertEquals(((List<?>) rows).size(), 1);
        Map<String, Object> app = (Map<String, Object>) ((List<?>) rows).get(0);
        Assert.assertEquals(id(app, "application_id"), application);
        Assert.assertEquals(id(app, "organization_id"), application);
        Assert.assertEquals(app.get("status"), status);
        if (note != null) Assert.assertEquals(app.get("review_note"), note);
    }

    private void upload(long application, String kind, Path file) {
        uploadType = kind;
        uploadFile = file;
        try {
            execute("POST", appPath("/documents"), null, token, params(application));
        } finally {
            uploadType = null;
            uploadFile = null;
        }
    }

    private Path png(String name, boolean revised) throws Exception {
        Path dir = EVIDENCE_ROOT.resolve("fixtures");
        Files.createDirectories(dir);
        byte[] content = java.util.Base64.getDecoder().decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHo0AAAAASUVORK5CYII=");
        // A harmless trailing QA marker makes the revision different.
        if (revised) {
            byte[] marker = ("QA corrected " + UUID.randomUUID()).getBytes(StandardCharsets.UTF_8);
            byte[] changed = java.util.Arrays.copyOf(content, content.length + marker.length);
            System.arraycopy(marker, 0, changed, content.length, marker.length);
            content = changed;
        }
        Path file = dir.resolve(name + ".png");
        Files.write(file, content);
        return file;
    }

    private String donationBody() {
        java.time.OffsetDateTime now = java.time.OffsetDateTime.now(java.time.ZoneOffset.UTC);
        return json.toJson(Map.of(
                "title", "MEAL215 QA draft", "category", "prepared_meal",
                "total_quantity", "5", "quantity_unit", "portions",
                "available_from", now.toString(),
                "pickup_deadline", now.plusHours(4).toString(),
                "pickup_address", "123 QA Test Road", "pickup_city", "Kurunegala",
                "status", "draft"));
    }

    // Business is tested on its actual write endpoint, not the NGO-only browse route.
    private void protectedOperation() {
        if (accountType.equals("business")) {
            execute("POST", "/api/v1/donations", donationBody(), token);
        } else {
            execute("GET", "/api/v1/donations", null, token);
        }
    }

    @DataProvider(name = "organizations", parallel = false)
    public Object[][] organizations() {
        return new Object[][]{{"business", "business_staff"}, {"ngo", "ngo_staff"}};
    }

    @Test(dataProvider = "organizations", singleThreaded = true)
    public void verificationLifecycle(String type, String role) throws Exception {
        accountType = type;
        testEmail = "qa.verify." + UUID.randomUUID().toString().replace("-", "") + "@example.com";

        adminToken = login(adminEmail, adminPassword);
        verifyStep("01_admin_login", () -> {
            success();
            Assert.assertEquals(nested(nested(responseObject(), "data"), "user").get("role"), "admin");
            Assert.assertFalse(lastBody.contains(adminPassword));
        });

        execute("POST", "/api/v1/auth/register", json.toJson(Map.of(
                "first_name", "QA", "last_name", "Verification", "email", testEmail,
                "password", password, "account_type", accountType)), null);
        verifyStep("02_register_applicant", () -> {
            Assert.assertEquals(lastStatus, "201");
            Assert.assertEquals(nested(responseObject(), "data").get("role"), role);
            assertNoPassword();
        });

        token = login(testEmail, password);
        verifyStep("03_applicant_login", this::success);

        execute("POST", "/api/v1/organization-applications", organization(), token);
        verifyStep("04_create_draft", () -> {
            Assert.assertEquals(lastStatus, "201");
            Assert.assertEquals(nested(responseObject(), "data").get("status"), "draft");
        });
        long application = id(nested(responseObject(), "data"), "application_id");

        protectedOperation();
        verifyStep("05_draft_restricted", () -> error(403, "FORBIDDEN"));

        Path invalid = EVIDENCE_ROOT.resolve("fixtures/invalid.txt");
        Files.createDirectories(invalid.getParent());
        Files.writeString(invalid, "This is an invalid QA document");
        upload(application, "registration_certificate", invalid);
        verifyStep("06_invalid_upload_rejected", () -> error(422, "VALIDATION_ERROR"));

        execute("GET", "/api/v1/organization-applications/me", null, token);
        verifyStep("07_failed_upload_preserves_draft", () -> ownStatus(application, "draft", null));

        String[] kinds = accountType.equals("business")
                ? new String[]{"registration_certificate", "food_premises_certificate", "trade_licence"}
                : new String[]{"registration_certificate"};
        Map<String, Long> documents = new java.util.LinkedHashMap<>();
        for (String kind : kinds) {
            upload(application, kind, png(type + "_" + kind, false));
            verifyStep("08_upload_" + kind, () -> {
                Assert.assertEquals(lastStatus, "201");
                Assert.assertEquals(nested(responseObject(), "data").get("document_type"), kind);
                Assert.assertTrue(id(nested(responseObject(), "data"), "document_id") > 0);
            });
            documents.put(kind, id(nested(responseObject(), "data"), "document_id"));
        }

        execute("POST", appPath("/submit"), null, token, params(application));
        verifyStep("09_submit", () -> {
            success();
            Assert.assertEquals(nested(responseObject(), "data").get("status"), "pending_verification");
        });

        protectedOperation();
        verifyStep("10_pending_restricted", () -> error(403, "FORBIDDEN"));

        execute("POST", adminPath("/decision"), json.toJson(Map.of(
                        "decision", "approved", "review_note", "QA attempt before document review")),
                adminToken, params(application));
        verifyStep("11_unreviewed_evidence_blocks_approval", () -> error(422, "DOCUMENT_NOT_APPROVED"));

        String reason = "QA correction required: replace the registration evidence.";
        execute("POST", adminPath("/reject"), json.toJson(Map.of("reason", reason)),
                adminToken, params(application));
        verifyStep("12_admin_rejects", () -> {
            success();
            Map<String, Object> d = nested(responseObject(), "data");
            Assert.assertEquals(d.get("status"), "rejected");
            Assert.assertTrue(id(d, "reviewed_by_user_id") > 0);
            Assert.assertNotNull(d.get("reviewed_at"));
        });

        token = login(testEmail, password);
        verifyStep("13_rejected_applicant_can_login", this::success);
        execute("GET", "/api/v1/organization-applications/me", null, token);
        verifyStep("14_rejection_feedback", () -> ownStatus(application, "rejected", reason));

        protectedOperation();
        verifyStep("15_rejected_restricted", () -> error(403, "FORBIDDEN"));

        execute("POST", appPath("/resubmit"), null, token, params(application));
        verifyStep("16_unchanged_evidence_blocks_resubmit", () -> error(422, "VALIDATION_ERROR"));

        long originalDocument = documents.get("registration_certificate");
        upload(application, "registration_certificate", png(type + "_corrected", true));
        verifyStep("17_corrected_evidence_upload", () -> {
            Assert.assertEquals(lastStatus, "201");
            Assert.assertNotEquals(id(nested(responseObject(), "data"), "document_id"), originalDocument);
        });
        documents.put("registration_certificate", id(nested(responseObject(), "data"), "document_id"));

        execute("POST", appPath("/resubmit"), null, token, params(application));
        verifyStep("18_resubmit_same_organization", () -> {
            success();
            Map<String, Object> d = nested(responseObject(), "data");
            Assert.assertEquals(id(d, "organization_id"), application);
            Assert.assertEquals(d.get("status"), "pending_verification");
        });

        for (Map.Entry<String, Long> document : documents.entrySet()) {
            execute("POST", adminPath("/documents/{document_id}/review"),
                    json.toJson(Map.of("decision", "approved", "review_note", "QA synthetic evidence reviewed")),
                    adminToken, Map.of("application_id", Long.toString(application),
                            "document_id", Long.toString(document.getValue())));
            verifyStep("19_review_" + document.getKey(), () -> {
                success();
                Assert.assertEquals(nested(responseObject(), "data").get("review_status"), "approved");
            });
        }

        execute("POST", adminPath("/decision"), json.toJson(Map.of(
                        "decision", "approved", "review_note", "QA approval of synthetic test organization")),
                adminToken, params(application));
        verifyStep("20_admin_approves", () -> {
            success();
            Assert.assertEquals(nested(responseObject(), "data").get("status"), "verified");
        });

        execute("GET", "/api/v1/organization-applications/me", null, token);
        verifyStep("21_verified_status", () -> ownStatus(application, "verified", null));

        protectedOperation();
        verifyStep("22_approved_access", () -> {
            Assert.assertEquals(lastStatus, accountType.equals("business") ? "201" : "200");
            assertNoPassword();
        });

        if (accountType.equals("business")) {
            execute("GET", "/api/v1/donations", null, token);
        } else {
            execute("POST", "/api/v1/donations", donationBody(), token);
        }
        verifyStep("23_wrong_organization_operation_denied", () -> error(403, "FORBIDDEN"));

        execute("GET", adminPath(""), null, adminToken, params(application));
        verifyStep("24_history_preserved", () -> {
            success();
            Map<String, Object> d = nested(responseObject(), "data");
            Assert.assertEquals(id(d, "organization_id"), application);
            Assert.assertTrue(d.get("submissions") instanceof List);
            Assert.assertTrue(((List<?>) d.get("submissions")).size() >= 2);
            Assert.assertTrue(d.get("reviews") instanceof List);
            List<?> reviews = (List<?>) d.get("reviews");
            Assert.assertTrue(reviews.stream().anyMatch(r -> "rejected".equals(((Map<?, ?>) r).get("decision"))));
            Assert.assertTrue(reviews.stream().anyMatch(r -> "approved".equals(((Map<?, ?>) r).get("decision"))));
            Assert.assertTrue(d.get("documents") instanceof List);
            List<?> history = (List<?>) d.get("documents");
            Assert.assertTrue(history.stream().anyMatch(r -> ((Number) ((Map<?, ?>) r).get("document_id")).longValue() == originalDocument));
        });

        execute("GET", adminPath(""), null, token, params(application));
        verifyStep("25_applicant_cannot_read_admin_details", () -> error(403, "FORBIDDEN"));
    }

    @AfterMethod(alwaysRun = true)
    public void closeBrowser(ITestResult result) throws Exception {
        try {
            if (!result.isSuccess() && driver != null) saveEvidence("flow_failure", "FAIL");
        } finally {
            if (driver != null) {
                try { driver.quit(); } finally { driver = null; }
            }
        }
    }
}
